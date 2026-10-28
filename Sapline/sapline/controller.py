"""The app's engine room: runs the EXP recorder in the background and keeps what the window shows.

The window (a web page) asks for /api/state about once a second and sends button presses as
small requests. Everything here is safe to call from the web server's threads.
"""
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque

from . import __version__, engine
from .config import APP_DIR, EXP_IDLE, UPDATE_EVERY
from .exp import ExpDays, ExpLog, ExpTracker
from .mobs import Mobs, parse_mobs
from .mobpics import MobPics
from .ocr import find_tesseract
from .recorder import Events, ExpRunner
from . import update as updater

SETTINGS = os.path.join(APP_DIR, 'settings.json')


class _Feed(Events):
    """Recorder -> controller."""
    def __init__(self, c):
        self.c = c

    def message(self, text):
        self.c.note(text, 'warn')

    def exp(self, summary):
        pass                                         # (the window reads the summary from the snapshot)


class Controller:
    def __init__(self):
        self.lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._settings_lock = threading.Lock()
        self.settings = self._load()
        self.tesseract = find_tesseract()
        self.engine = engine.mode() if self.tesseract else 'none'
        self._tess_check = 0                         # when we last looked for a newly installed Tesseract
        self.exp_days = ExpDays(os.path.join('scans', 'exp_days.json'))   # EXP gained each day (kept by Reset)
        self.exp_log = ExpLog(os.path.join('scans', 'exp_log.json'))     # one line per hunting run (the Runs tab)
        self.mobs = Mobs(os.path.join(APP_DIR, 'mobs.txt'))   # names for the kills counted (a list the owner keeps)
        self.mobs.ensure()
        self.mobpics = MobPics(os.path.join(APP_DIR, 'scans', 'mobs'), os.path.join(APP_DIR, 'scans', 'fight'))   # a picture of each mob killed
        self.exp = ExpTracker(on_gain=self.exp_days.add, on_run=self._log_run, namer=self.mobs.name)   # kept across stop/start: Reset clears it
        self.exp.idle = int(self.settings['idle_min']) * 60
        self.exp_runner = None
        self.seq = 0
        self.events = deque(maxlen=400)              # notes, newest last
        self.last_seen = time.time()                 # when the window last asked for news
        # updates: only the installed app (Sapline.exe) can install one; the zip version is told where to get it
        self.frozen = bool(getattr(sys, 'frozen', False))
        self.update_info = {'state': 'checking'}
        self._update_at = 0
        self.quit_requested = False                  # set when an update is about to install: the window closes
        if self.frozen:
            self._after_update()

    # --- settings ---
    def _load(self):
        try:
            with open(SETTINGS, encoding='utf-8') as f:
                s = json.load(f)
        except (OSError, ValueError):
            s = {}
        s.setdefault('monitor', 1)
        s.setdefault('exp', True)                    # record EXP as soon as the app opens
        s.setdefault('exp_log', True)                # keep the run log (the Runs tab's "Log my runs" switch)
        s.setdefault('idle_min', EXP_IDLE // 60)     # minutes without EXP before the clock pauses
        s['fight_pics'] = False                      # save whole screenshots around each kill (for tuning): off at every start
        return s

    def _save(self):
        try:
            with self._settings_lock:                # two changes at once must not write over each other
                with open(SETTINGS + '.tmp', 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, indent=1)
                os.replace(SETTINGS + '.tmp', SETTINGS)   # never half a file
        except OSError:
            pass

    # --- shared state ---
    def push(self, kind, **data):
        with self.lock:
            self.seq += 1
            self.events.append(dict(seq=self.seq, kind=kind, **data))

    def note(self, text, level='info'):
        self.push('note', text=text, level=level, t=time.time())

    def _look_for_tesseract(self):
        """Installed while the app was open? Then it's ready without a restart."""
        if find_tesseract():
            self.engine = engine.mode()               # can take a few seconds (a safety test): not on the window's request
            self.tesseract = True
            self.note('Tesseract found: map names and mesos are read from now on.')

    # --- updates ---
    def check_update(self, wait=False):
        """Look for a newer version in the background (or right away with wait=True)."""
        self._update_at = time.time()

        def look():
            info = updater.check()
            if self.update_info.get('state') not in ('downloading', 'installing'):
                self.update_info = dict(info, can_install=self.frozen)
        if wait:
            look()
        else:
            threading.Thread(target=look, daemon=True).start()
        return {'ok': True}

    PENDING = 'pending.json'                         # updates/pending.json: an update was started (from, to, when)

    def _after_update(self):
        """The installed app's start: say how the last update went (updates/pending.json was written when it
        started: if this is the version it aimed for, it worked; otherwise the install log says what happened),
        then drop the setup file and script, keeping the logs for reading."""
        folder = os.path.join(APP_DIR, 'updates')
        pending = os.path.join(folder, self.PENDING)
        try:
            with open(pending, encoding='utf-8') as f:
                want = json.load(f)
        except (OSError, ValueError):
            want = None
        if want:
            if not updater.newer(str(want.get('to', '')), __version__):
                self.note(f'Updated to Sapline {__version__}.')
            else:
                why = ''
                try:
                    with open(os.path.join(folder, updater.INSTALL_LOG), encoding='utf-8-sig') as f:
                        why = '; '.join(line[20:].strip() for line in f.read().splitlines()[-3:] if len(line) > 20)
                except OSError:
                    pass
                self.note(f"The update to {want.get('to')} did not install ({why or 'the install script never ran'}). "
                          f"The files install.log and setup.log in the folder updates (next to Sapline.exe) say why.",
                          'error')
        for name in os.listdir(folder) if os.path.isdir(folder) else []:
            if name.lower().endswith('.exe') or name in (updater.SCRIPT, self.PENDING):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass

    def install_update(self):
        """Download the new version, check its fingerprint, and hand over to its setup (which restarts us)."""
        if not self.frozen:
            return {'ok': False, 'error': 'This copy runs from the zip folder: download the new version from the release page.'}
        with self.lock:                              # a double click must not start two downloads
            info = self.update_info
            if info.get('state') != 'available':
                return {'ok': False, 'error': 'No update to install.'}
            self.update_info = dict(info, state='downloading')

        def go():
            try:
                folder = os.path.join(APP_DIR, 'updates')
                path = updater.download(info, folder)
                self.update_info = dict(info, state='installing')
                self.note('Installing the update. Sapline closes now and opens again by itself in a minute.')
                with open(os.path.join(folder, self.PENDING), 'w', encoding='utf-8') as f:
                    json.dump({'from': __version__, 'to': info['version'], 't': time.time()}, f)
                updater.start_install(path, app_exe=sys.executable)
                self.quit_requested = True
            except (OSError, ValueError) as e:
                self.update_info = dict(info, state='available', error=f'The update could not be installed: {e}')
                self.note(f'The update could not be installed: {e}', 'error')
        threading.Thread(target=go, daemon=True).start()
        return {'ok': True}

    def snapshot(self, since=0):
        if time.time() - self._update_at > UPDATE_EVERY:
            self.check_update()
        if not self.tesseract and time.time() - self._tess_check > 5:
            self._tess_check = time.time()
            threading.Thread(target=self._look_for_tesseract, daemon=True).start()
        r = self.exp_runner
        with self.lock:
            self.last_seen = time.time()
            settings = dict(self.settings)
            return dict(version=__version__, engine=self.engine, tesseract=self.tesseract, update=self.update_info,
                        settings=settings, exp=self._with_pics(self.exp.summary()), exp_days=self.exp_days.last(7), exp_log=self.exp_log.list(),
                        exp_on=bool(r), exp_found=bool(r and r.found), exp_unread=r.watcher.unread if r else 0,
                        seq=self.seq, events=[e for e in self.events if e['seq'] > since])

    # --- EXP: Start/Stop (the `exp` setting) ---
    def _with_pics(self, x):
        """The EXP summary with `pic` on each mob (is there a picture of it in scans/mobs?)."""
        if x:
            for ks in (x.get('kills') or [], (x.get('run') or {}).get('kills') or []):
                for k in ks:
                    k['pic'] = k['exp'] in self.mobpics.have
        return x

    def exp_start(self):
        with self._start_lock:
            if self.exp_runner:
                return {'ok': True}
            r = self.exp_runner = ExpRunner(self.exp, monitor=int(self.settings['monitor']), events=_Feed(self), mobpics=self.mobpics,
                                            fight=lambda: bool(self.settings.get('fight_pics')))
            self.exp.resume()                            # (the time it was stopped doesn't count)

        def run():
            try:
                r.run()
            except Exception as e:
                self.note(f'EXP recording stopped: {type(e).__name__}: {e}. Please report this line.', 'error')
            finally:
                if self.exp_runner is r:
                    self.exp_runner = None
        threading.Thread(target=run, daemon=True, name='exp').start()
        return {'ok': True}

    def exp_stop(self):
        r, self.exp_runner = self.exp_runner, None
        if r:
            r.stop()
        self.exp.pause()                                 # the numbers stay as they were, not sinking while stopped
        return {'ok': True}

    def _log_run(self, e):
        if self.settings.get('exp_log', True):
            self.exp_log.add(e)

    def mob_name(self, d):
        """The "Name this mob" box: the name goes into mobs.txt (replacing a line with the same EXP), or
        action "forget" drops a wrong picture so the next clear kill brings a new one."""
        exp = int(d.get('exp'))
        if d.get('action') == 'forget':
            self.mobpics.forget(exp)
            return {'ok': True}
        name = ' '.join(str(d.get('name', '')).split())
        if not 1 <= len(name) <= 40 or '|' in name or not 0 < exp < 100_000_000:
            return {'ok': False, 'error': 'A name is 1 to 40 letters, without |.'}
        self.mobs.ensure()
        with open(self.mobs.path, encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
        keep = [ln for ln in lines if exp not in parse_mobs(ln) or ln.lstrip().startswith('#')]
        with open(self.mobs.path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(keep + [f'{name} | {exp}']) + '\n')
        self.mobs.checked = 0                        # (read again at once)
        return {'ok': True}

    def exp_log_edit(self, d):
        """The run log's Rename and Delete buttons."""
        ok = self.exp_log.rename(str(d.get('id')), d.get('name')) if d.get('action') == 'rename' else \
            self.exp_log.delete(str(d.get('id'))) if d.get('action') == 'delete' else False
        return {'ok': ok} if ok else {'ok': False, 'error': 'That line is not in the run log any more.'}

    def exp_reset(self):
        self.exp.reset()
        self.note('EXP tracking restarted.')
        return {'ok': True}

    def autostart(self):
        """When the app opens: start recording EXP, unless switched off in Options."""
        if self.settings.get('exp', True):
            self.exp_start()

    def update(self, d):
        """Settings from the window: monitor, exp, exp_log, idle_min, fight_pics."""
        for k, conv in (('monitor', int), ('exp', bool), ('exp_log', bool), ('idle_min', int), ('fight_pics', bool)):
            if k in d:
                self.settings[k] = conv(d[k])
        if 'idle_min' in d:
            if not 1 <= self.settings['idle_min'] <= 30:
                self.settings['idle_min'] = min(30, max(1, self.settings['idle_min']))
            self.exp.idle = self.settings['idle_min'] * 60
        if 'exp' in d:
            if self.settings['exp']:
                self.exp_start()
                self.note('Recording your EXP.')
            else:
                self.exp_stop()
                self.note('EXP recording stopped.')
        if 'monitor' in d and self.exp_runner:
            self.note('The new screen is used next time you press Start.')
        self._save()
        return {'ok': True}

    def open_scans(self):
        path = os.path.join(APP_DIR, 'scans')
        os.makedirs(path, exist_ok=True)
        if sys.platform == 'win32':
            os.startfile(path)
        return {'ok': True, 'path': path}

    def install_tesseract(self):
        if sys.platform != 'win32':
            return {'ok': False, 'error': 'Only on Windows.'}
        cmd = ('winget install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements'
               ' & echo. & echo Done. Close this window; Sapline is ready. & pause')
        subprocess.Popen(['cmd', '/c', cmd], creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
        self.note('Installing Tesseract in a separate window. Click Yes if Windows asks. Sapline notices when it is done.')
        return {'ok': True}

    def shutdown(self):
        self.exp_stop()
        self.exp.end_run()                           # (the run so far goes into the run log)
        self.exp_days.flush()
        self._save()
