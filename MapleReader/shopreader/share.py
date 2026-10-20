"""Share with friends: sends what you scan to the group's market (maple.vendormarket.app).

It follows scans/all_scans.txt and sends every new line, then any item pictures the group doesn't
have yet. Where it got to is remembered in scans/share_state.json, so nothing is lost or sent twice
when you're offline, the server is down, or you close the app: it simply carries on later.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

from . import __version__
from .icons import ICON_DIR

STATE = os.path.join('scans', 'share_state.json')
ALL = os.path.join('scans', 'all_scans.txt')
BATCH = 2000
DEFAULT_SERVER = 'https://maple.vendormarket.app'


def _clean_server(url):
    url = (url or '').strip().rstrip('/')
    if url and not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


class Sharer:
    def __init__(self, server, key, on_change=None):
        self.server, self.key = _clean_server(server), (key or '').strip()
        self.on_change = on_change or (lambda: None)
        self.status = dict(on=True, state='starting', sent=0, last_ok=None, error=None, who=None)
        self._stop = threading.Event()
        self.state = self._load()
        threading.Thread(target=self._run, daemon=True).start()

    # --- remembering where we got to (per server and key) ---
    def _slot(self):
        return self.server + '|' + self.key[-8:]

    def _load(self):
        try:
            with open(STATE, encoding='utf-8') as f:
                all_ = json.load(f)
        except (OSError, ValueError):
            all_ = {}
        return all_.get(self._slot(), {'offset': 0, 'icons': {}, 'sent': 0})

    def _save(self):
        try:
            with open(STATE, encoding='utf-8') as f:
                all_ = json.load(f)
        except (OSError, ValueError):
            all_ = {}
        all_[self._slot()] = self.state
        os.makedirs('scans', exist_ok=True)
        tmp = STATE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(all_, f)
        os.replace(tmp, STATE)

    def stop(self):
        self._stop.set()
        self.status.update(on=False, state='off')

    def _set(self, **kw):
        self.status.update(kw)
        self.on_change()

    # --- talking to the server ---
    def _post(self, path, body, ctype):
        req = urllib.request.Request(self.server + path, data=body, method='POST', headers={
            'Authorization': 'Bearer ' + self.key, 'Content-Type': ctype,
            'User-Agent': f'MapleReader/{__version__}'})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode('utf-8'))

    def _send_lines(self):
        """Send what's new in all_scans.txt. Returns True if there may be more right away."""
        try:
            size = os.path.getsize(ALL)
        except OSError:
            return False
        if self.state['offset'] > size:              # the file was replaced: start over (the server skips repeats)
            self.state['offset'] = 0
        with open(ALL, 'rb') as f:
            f.seek(self.state['offset'])
            data = f.read(1_500_000)
        cut = data.rfind(b'\n')
        if cut < 0:
            return False
        chunk = data[:cut + 1]
        lines = [ln for ln in chunk.decode('utf-8', 'replace').splitlines() if ln.strip()]
        for i in range(0, len(lines), BATCH):
            r = self._post('/api/upload', json.dumps({'lines': lines[i:i + BATCH]}).encode('utf-8'), 'application/json')
            self.state['sent'] += r.get('added', 0)
            self.status['who'] = r.get('who')
        self.state['offset'] += len(chunk)
        self._save()
        return self.state['offset'] < size

    def _send_icons(self):
        try:
            with open(os.path.join(ICON_DIR, 'index.json'), encoding='utf-8') as f:
                idx = json.load(f)
        except (OSError, ValueError):
            return
        for name, kind in idx.items():
            if self._stop.is_set():
                return
            if self.state['icons'].get(name) in ('normal', kind):
                continue                             # the group already has this one (or a clearer one)
            try:
                with open(os.path.join(ICON_DIR, name + '.png'), 'rb') as f:
                    png = f.read()
            except OSError:
                continue
            try:
                self._post(f'/api/icon?slug={name}&kind={kind}', png, 'image/png')
            except urllib.error.HTTPError as e:
                if e.code in (401, 429) or e.code >= 500:
                    raise                            # key, rate or server trouble: the loop retries later
                # any other refusal is about this one picture (too big, odd name): skip it, keep going
            self.state['icons'][name] = kind
            self._save()

    def _run(self):
        wait = 1
        while not self._stop.is_set():
            if not self.server or not self.key:
                self._set(state='needs-key', error='Enter the market address and your key.')
                return
            try:
                more = self._send_lines()
                self._send_icons()
                self._set(state='ok', error=None, sent=self.state['sent'], last_ok=time.time())
                wait = 0.2 if more else 3
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    self._set(state='bad-key', error='The market did not accept your key. Check it with whoever runs the market.')
                    return                           # no point retrying until the key changes
                self._set(state='retrying', error=f'The market answered {e.code}. Trying again shortly.')
                wait = min(60, max(5, wait * 2))
            except (urllib.error.URLError, OSError, ValueError) as e:
                reason = getattr(e, 'reason', e)
                self._set(state='offline', error=f"Can't reach the market ({reason}). Your scans are kept and sent later.")
                wait = min(60, max(5, wait * 2))
            self._stop.wait(wait)


def fetch_rows(server, start):
    """For the app's Market tab: the group's listings after `start` (read-only, no key needed)."""
    url = _clean_server(server) + f'/api/rows?from={int(start)}'
    req = urllib.request.Request(url, headers={'User-Agent': f'MapleReader/{__version__}'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))


def fetch_icon(server, name):
    req = urllib.request.Request(_clean_server(server) + f'/icons/{name}.png',
                                 headers={'User-Agent': f'MapleReader/{__version__}'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()
