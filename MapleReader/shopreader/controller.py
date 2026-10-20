"""The app's engine room: runs the scanner in the background and keeps what the window shows.

The window (a web page) asks for /api/state about once a second and sends button presses as
small requests. Everything here is safe to call from the web server's threads.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import deque

from . import __version__, engine
from .config import APP_DIR, UPDATE_EVERY, VOLUME
from .icons import slug
from .location import RoomWatcher, read_channel
from .names import load_items
from .ocr import find_tesseract
from .rows import parse_frame
from .scanner import Events, Scanner
from . import share
from . import update as updater

SETTINGS = os.path.join(APP_DIR, 'settings.json')


class _Feed(Events):
    """Scanner -> controller."""
    def __init__(self, c):
        self.c = c

    def message(self, text):
        self.c.note(text, 'warn')

    def status(self, what):
        self.c.set(status=what)

    def channel(self, ch, auto):
        self.c.set(channel=ch)
        self.c.note(f'Channel {ch}, read from the Change Channel window.')

    def room(self, room):
        self.c.set(room=room)
        if not room:
            self.c.note('Room not read. Is the minimap open? You can type the room instead.', 'warn')

    def shop(self, name, rows_seen):
        self.c.set(shop=name, shop_rows=rows_seen)

    def saved(self, rows, room, ch, total):
        now = time.time()
        self.c.set(total=total, room=room, channel=ch)
        self.c.push('saved', rows=[dict(item=r['item'], each=r['each'], shop=r['shop'], sold=bool(r.get('sold')),
                                        room=room, ch=ch, icon=slug(r['item']), t=now) for r in rows])


class Controller:
    def __init__(self):
        self.lock = threading.Lock()
        self._start_lock = threading.Lock()
        self.settings = self._load()
        self.tesseract = find_tesseract()
        self.engine = engine.mode() if self.tesseract else 'none'
        self._tess_check = 0                         # when we last looked for a newly installed Tesseract
        self.scanner = None
        self.seq = 0
        self.events = deque(maxlen=400)              # saved rows and notes, newest last
        self.state = dict(watching=False, status='stopped', channel=0, room=0, shop=None, shop_rows=0,
                          total=0, started=None)
        self.last_seen = time.time()                 # when the window last asked for news
        self.sharer = None
        self._share_restart()
        # updates: only the installed app (MapleReader.exe) can install one; the zip version is told where to get it
        self.frozen = bool(getattr(sys, 'frozen', False))
        self.update_info = {'state': 'checking'}
        self._update_at = 0
        self.quit_requested = False                  # set when an update is about to install: the window closes
        if self.frozen:                              # an earlier update's setup file is no longer needed
            shutil.rmtree(os.path.join(APP_DIR, 'updates'), ignore_errors=True)

    # --- settings ---
    def _load(self):
        try:
            with open(SETTINGS, encoding='utf-8') as f:
                s = json.load(f)
        except (OSError, ValueError):
            s = {}
        s.setdefault('volume', VOLUME)
        s.setdefault('quiet', False)
        s.setdefault('monitor', 1)
        s.setdefault('share_on', False)
        s.setdefault('share_server', share.DEFAULT_SERVER)
        s.setdefault('share_key', '')
        s.setdefault('auto_start', True)             # start watching as soon as the app opens
        return s

    def _save(self):
        try:
            with open(SETTINGS, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=1)
        except OSError:
            pass

    # --- sharing with friends ---
    def _share_restart(self):
        if self.sharer:
            self.sharer.stop()
            self.sharer = None
        s = self.settings
        if s.get('share_on') and s.get('share_key'):
            self.sharer = share.Sharer(s['share_server'], s['share_key'])

    def share_status(self):
        s = self.settings
        st = dict(self.sharer.status) if self.sharer else dict(on=False, state='off' if s.get('share_on') is False else 'needs-key')
        k = s.get('share_key', '')
        st.update(server=s.get('share_server'), key_hint=('••••' + k[-4:]) if k else '', enabled=bool(s.get('share_on')))
        return st

    # --- shared state ---
    def set(self, **kw):
        with self.lock:
            self.state.update(kw)

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
            self.note('Tesseract found. Press Start watching.')

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

    def install_update(self):
        """Download the new version, check its fingerprint, and hand over to its setup (which restarts us)."""
        info = self.update_info
        if info.get('state') != 'available':
            return {'ok': False, 'error': 'No update to install.'}
        if not self.frozen:
            return {'ok': False, 'error': 'This copy runs from the zip folder: download the new version from the release page.'}

        def go():
            self.update_info = dict(info, state='downloading')
            try:
                path = updater.download(info, os.path.join(APP_DIR, 'updates'))
                self.update_info = dict(info, state='installing')
                self.note('Installing the update. MapleReader closes now and opens again by itself in a minute.')
                updater.start_install(path)
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
        with self.lock:
            self.last_seen = time.time()
            settings = {k: v for k, v in self.settings.items() if k != 'share_key'}   # the key never leaves the app
            return dict(self.state, version=__version__, engine=self.engine, tesseract=self.tesseract, update=self.update_info,
                        settings=settings, share=self.share_status(), seq=self.seq,
                        events=[e for e in self.events if e['seq'] > since])

    # --- buttons ---
    def start(self, channel=0):
        if not self.tesseract:
            return {'ok': False, 'error': 'Tesseract is not installed.'}
        with self._start_lock:                       # two quick clicks must not start two scanners
            if self.scanner:
                return {'ok': True}
            items = load_items(os.path.join(APP_DIR, 'items.txt'))
            sc = Scanner(items, int(channel or 0), monitor=int(self.settings['monitor']),
                         volume=float(self.settings['volume']), quiet=bool(self.settings['quiet']), events=_Feed(self))
            self.scanner = sc
        self.set(watching=True, status='looking', channel=sc.state['ch'], room=0, shop=None, shop_rows=0, total=0,
                 started=time.time())
        self.note('Watching your screen.' + ('' if sc.state['ch'] else ' Open the Change Channel window once so I can read your channel.'))

        def run():
            try:
                sc.run()
            except Exception as e:                   # never stop silently
                self.note(f'Scanning stopped: {type(e).__name__}: {e}. Send this line to Claude.', 'error')
            finally:
                if self.scanner is sc:
                    self.scanner = None
                    self.set(watching=False, status='stopped')
        threading.Thread(target=run, daemon=True).start()
        return {'ok': True}

    def autostart(self):
        """When the app opens: start watching straight away, unless that's switched off in Settings."""
        if self.settings.get('auto_start', True) and self.tesseract:
            self.start()

    def stop(self):
        sc, self.scanner = self.scanner, None
        if sc:
            sc.stop()
            self.set(watching=False, status='stopped', shop=None)
            self.note(f'Stopped. {self.state["total"]} listings saved this session.')
        return {'ok': True}

    def update(self, d):
        """Settings and corrections from the window: channel, room, volume, quiet, monitor."""
        if 'channel' in d:
            ch = int(d['channel'])
            if not 1 <= ch <= 40:
                return {'ok': False, 'error': 'Channel must be 1 to 40.'}
            self.set(channel=ch)
            if self.scanner:
                self.scanner.set_channel(ch)
            self.note(f'Channel set to {ch}.')
        if 'room' in d:
            rm = int(d['room'])
            if not 0 <= rm <= 40:
                return {'ok': False, 'error': 'Room must be 0 (unknown) to 40.'}
            self.set(room=rm)
            if self.scanner:
                self.scanner.set_room(rm)
            self.note(f'Room set to {rm}.')
        for k, conv in (('volume', float), ('quiet', bool), ('monitor', int), ('auto_start', bool)):
            if k in d:
                self.settings[k] = conv(d[k])
        if self.scanner and ('volume' in d or 'quiet' in d):
            self.scanner.set_sound(volume=self.settings['volume'], quiet=self.settings['quiet'])
        if 'monitor' in d and self.scanner:
            self.note('The new screen is used next time you press Start.')
        if any(k in d for k in ('share_on', 'share_server', 'share_key')):
            if 'share_server' in d:
                self.settings['share_server'] = share._clean_server(d['share_server']) or share.DEFAULT_SERVER
            if 'share_key' in d and str(d['share_key']).strip():
                self.settings['share_key'] = str(d['share_key']).strip()
            if 'share_on' in d:
                self.settings['share_on'] = bool(d['share_on'])
            if self.settings['share_on'] and not self.settings.get('share_key'):
                self._save()
                return {'ok': False, 'error': 'Type the key you were given first.'}
            self._share_restart()
            self.note('Sharing with friends is on.' if self.settings['share_on'] else 'Sharing with friends is off.')
        self._save()
        return {'ok': True}

    def read_picture(self, data):
        """'Read a screenshot': what the reader sees in one picture."""
        if not self.tesseract:
            return {'ok': False, 'error': 'Tesseract is not installed.'}
        from PIL import Image
        try:
            im = Image.open(io.BytesIO(data)).convert('RGB')
        except Exception:
            return {'ok': False, 'error': 'That file is not a picture.'}
        rows, _, _ = parse_frame(im, load_items(os.path.join(APP_DIR, 'items.txt')))
        room = RoomWatcher(keep_picture=False).update(im, [], force=True)
        ch = None if rows else read_channel(im)
        return {'ok': True, 'room': room, 'channel': ch,
                'rows': [dict(item=r['item'], each=r['each'], shop=r['shop'], sold=bool(r.get('sold'))) for r in rows]}

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
               ' & echo. & echo Done. Close this window; MapleReader is ready. & pause')
        subprocess.Popen(['cmd', '/c', cmd], creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
        self.note('Installing Tesseract in a separate window. Click Yes if Windows asks. MapleReader notices when it is done.')
        return {'ok': True}

    def status_line(self):
        """For the market's live banner."""
        s = self.state
        return dict(watching=s['watching'], channel=s['channel'], room=s['room'], total=s['total'], shop=s['shop'])

    def shared_rows(self, start):
        """Friends' listings for the Market tab, read from the group's market."""
        if not self.settings.get('share_on'):
            return {'configured': False}
        try:
            return share.fetch_rows(self.settings['share_server'], start)
        except Exception as e:
            return {'text': '', 'next': start, 'more': False, 'reset': False, 'error': str(e)}

    def shutdown(self):
        if self.sharer:
            self.sharer.stop()
        if self.scanner:
            self.scanner.stop()
        self._save()
