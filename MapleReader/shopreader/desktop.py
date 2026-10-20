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
                                     '--no-default-browser-check', '--window-size=1240,860', '--disable-features=Translate'])
        except OSError:
            pass
    webbrowser.open(url)
    return None


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
    ctl = Controller()
    srv = MarketServer(controller=ctl)
    url = srv.start()
    if not url:
        _message('MapleReader could not start: the ports it uses (8765 to 8770) are all busy.\n'
                 'Close other copies of MapleReader, or restart the PC, and try again.')
        return
    proc, opened = open_window(url), time.time()
    try:
        while True:
            time.sleep(1)
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


if __name__ == '__main__':
    run()
    sys.exit(0)
