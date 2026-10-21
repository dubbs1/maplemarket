"""MapleReader as a desktop app: the scanner and the market in one window.

Starts the scanner's controls and the market on this PC (http://127.0.0.1:8765), then shows them in
an app window: Microsoft Edge in "app mode" (no address bar or tabs), which every Windows 10/11 PC
has. If Edge isn't there it tries Chrome, then your normal browser. Closing the window closes
MapleReader.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from .config import APP_DIR

BROWSERS = [r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe',
            r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe',
            r'%LocalAppData%\Microsoft\Edge\Application\msedge.exe',
            r'%ProgramFiles%\Google\Chrome\Application\chrome.exe',
            r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe',
            r'%LocalAppData%\Google\Chrome\Application\chrome.exe']
QUIET_FOR = 90                     # no word from the window this long (seconds) = it was closed
WINDOW_TITLE = 'Maple Market'      # the page's <title> (the self-check looks for it; the window lock's fallback)
WINDOW_SIZE = (1240, 860)          # the app window, outer size: the page is drawn for exactly this


def _profile_dir():
    """The app window's own browser profile (its saved market data lives here). Kept out of OneDrive."""
    base = os.environ.get('LOCALAPPDATA') or APP_DIR
    return os.path.join(base, 'MapleReader', 'window')


def _find_browser():
    for p in BROWSERS:
        p = os.path.expandvars(p)
        if os.path.isfile(p):
            return p
    return None


def _message(text):
    """A plain Windows message box (there is no console to print to)."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, 'MapleReader', 0x40)
    except Exception:
        pass


def open_window(url):
    """Show the app window. Returns the browser process, or None if it opened in a normal browser."""
    exe = _find_browser()
    if exe:
        try:
            return subprocess.Popen([exe, f'--app={url}', f'--user-data-dir={_profile_dir()}', '--no-first-run',
                                     '--no-default-browser-check', f'--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}', '--disable-features=Translate'])
        except OSError:
            pass
    webbrowser.open(url)
    return None


def _lock_window(proc, title, wait=25):
    """Windows: once the app window is up, take away its resize border and Maximise button, so the page (drawn for
    exactly this window) never has to squeeze or stretch. The window is the one owned by the browser we started;
    if that browser handed the window to a copy already running, the one with our title. Quietly does nothing
    if it can't (the window is then simply resizable)."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        import ctypes.wintypes as wt
        u = ctypes.windll.user32
        GWL_STYLE, WS_THICKFRAME, WS_MAXIMIZEBOX = -16, 0x00040000, 0x00010000
        SWP_NOMOVE, SWP_NOZORDER, SWP_FRAMECHANGED = 0x2, 0x4, 0x20
        buf, pid, found = ctypes.create_unicode_buffer(len(title) + 1), wt.DWORD(), []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        def each(hwnd, by_pid):
            if u.IsWindowVisible(hwnd) and not u.GetParent(hwnd):
                if by_pid:
                    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value == proc.pid and u.GetWindowTextLengthW(hwnd):
                        found.append(hwnd)
                elif u.GetWindowTextW(hwnd, buf, len(title) + 1) and buf.value == title:
                    found.append(hwnd)
            return True
        end = time.time() + wait
        while time.time() < end and not found:
            time.sleep(1)
            u.EnumWindows(each, 1 if proc.poll() is None else 0)
        if found:
            style = u.GetWindowLongW(found[0], GWL_STYLE)
            u.SetWindowLongW(found[0], GWL_STYLE, style & ~(WS_THICKFRAME | WS_MAXIMIZEBOX))
            u.SetWindowPos(found[0], 0, 0, 0, WINDOW_SIZE[0], WINDOW_SIZE[1], SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass


def _running_app(port=8765):
    """Is a MapleReader app already serving? Then just open another window onto it."""
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/state', timeout=1) as r:
            return 'version' in json.loads(r.read().decode())
    except Exception:
        return False


def run():
    os.chdir(APP_DIR)                                # scans, settings and pictures live next to the app
    if _running_app():
        open_window('http://127.0.0.1:8765/')
        return
    from .controller import Controller
    from .market_server import MarketServer
    from .migrate import first_run
    moved = first_run(APP_DIR) if getattr(sys, 'frozen', False) else None   # the installed app's first run
    ctl = Controller()
    if moved:
        ctl.note(moved)
    srv = MarketServer(controller=ctl)
    url = srv.start()
    if not url:
        _message('MapleReader could not start: the ports it uses (8765 to 8770) are all busy.\n'
                 'Close other copies of MapleReader, or restart the PC, and try again.')
        return
    if srv.shared:                                   # a market window without the scanner (market.bat) holds the port
        _message('MapleReader is already open as a market window (market.bat).\n'
                 'Close that black window, then start MapleReader again.')
        ctl.shutdown()
        return
    ctl.autostart()
    proc, opened = open_window(url), time.time()
    if proc is not None:                             # one size, not resizable
        threading.Thread(target=_lock_window, args=(proc, WINDOW_TITLE), daemon=True).start()
    try:
        while True:
            time.sleep(1)
            if ctl.quit_requested:                   # an update is installing: close the window and step aside
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                break
            if proc is not None and proc.poll() is not None:
                if time.time() - opened > 5:
                    break                            # the app window was closed
                proc = None                          # the browser handed the window over: watch for news instead
            if proc is None and time.time() - ctl.last_seen > QUIET_FOR and time.time() - opened > QUIET_FOR:
                break                                # the page has stopped asking: its window was closed
    except KeyboardInterrupt:
        pass
    finally:
        ctl.shutdown()
        srv.stop()


def self_check(result_path):
    """MapleReader.exe --self-check result.txt: start the app's parts in a scratch folder, ask them what the window
    would ask, and write what happened (the exe has no console). Exit code 0 = all good. Used by the automatic
    builds, and handy on a PC where the app won't start."""
    import tempfile
    import traceback
    lines, good = [], False
    try:
        work = tempfile.mkdtemp(prefix='maplereader_check_')
        os.environ.setdefault('MAPLEREADER_UPDATE_API', 'off')
        from . import config, controller, market_server
        from .ocr import find_tesseract
        config.APP_DIR = controller.APP_DIR = market_server.APP_DIR = work
        controller.SETTINGS = os.path.join(work, 'settings.json')
        os.chdir(work)
        lines.append(f'tesseract found: {find_tesseract()}')
        ctl = controller.Controller()
        srv = market_server.MarketServer(controller=ctl, ports=range(8780, 8786))
        url = srv.start()
        with urllib.request.urlopen(url + 'api/state', timeout=10) as r:
            state = json.loads(r.read().decode())
        with urllib.request.urlopen(url, timeout=10) as r:
            page = r.read().decode('utf-8', 'replace')
        from .exp_font import GLYPHS
        lines += [f"version {state['version']}", f"text reader: {state['engine']}", f'page: {len(page)} characters',
                  f"EXP digit shapes: {''.join(sorted(GLYPHS.get('small', {})))}"]
        good = (bool(state['version']) and WINDOW_TITLE in page and state['tesseract'] and
                state['engine'] in ('fast', 'slow') and 'exp' in state and len(GLYPHS.get('small', {})) >= 10)
        srv.stop()
        ctl.shutdown()
    except Exception:
        lines.append(traceback.format_exc())
    lines.append('SELF-CHECK PASSED' if good else 'SELF-CHECK FAILED')
    with open(result_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return 0 if good else 1


if __name__ == '__main__':
    run()
    sys.exit(0)
