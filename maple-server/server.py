"""Maple Classic Market - the group's shared market (maple.vendormarket.app).

Friends' MapleReader apps send the listings they scan here (each with a personal key); everyone's
market page reads them back. Plain Python 3, no add-ons: one file, a SQLite database, a folder of
item pictures. It listens on 127.0.0.1 only; the web front door (nginx / Caddy / Cloudflare tunnel)
passes maple.vendormarket.app to it.

Settings come from the environment (see /etc/maple-market.env):
  MAPLE_PORT   port to listen on (default 8790)
  MAPLE_DATA   folder for the database, keys and pictures (default ./data)
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get('MAPLE_DATA') or os.path.join(HERE, 'data')
PORT = int(os.environ.get('MAPLE_PORT') or 8790)
PAGE = os.path.join(HERE, 'market.html')
ICONS = os.path.join(DATA, 'icons')
KEYS = os.path.join(DATA, 'keys.json')

MAX_BODY = 2_000_000              # bytes per upload
MAX_LINES = 5000                  # lines per upload
MAX_ICON = 100_000                # bytes per picture
PER_MINUTE = 60                   # row uploads per key per minute
ICONS_PER_MINUTE = 300            # picture uploads per key per minute (a first share sends many)
SCANNING_WINDOW = 10 * 60         # "scanning now" = sent something in the last 10 minutes
FEED_CHUNK = 5000                 # lines per /api/rows answer

_db_lock = threading.Lock()
_rate_lock = threading.Lock()
_state = {'keys': {}, 'keys_mtime': None, 'recent': {}, 'rate': {}}


# ---------- storage ----------
def db():
    os.makedirs(DATA, exist_ok=True)
    con = sqlite3.connect(os.path.join(DATA, 'market.db'), check_same_thread=False)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS rows (id INTEGER PRIMARY KEY AUTOINCREMENT, h TEXT UNIQUE, '
                'line TEXT NOT NULL, who TEXT NOT NULL, at REAL NOT NULL)')
    con.execute('CREATE INDEX IF NOT EXISTS rows_who ON rows(who)')
    con.commit()
    return con


def hash_key(key):
    return hashlib.sha256(key.strip().encode('utf-8')).hexdigest()


def load_keys():
    """keys.json maps hashed key -> {name, active}. Re-read whenever manage.py changes it."""
    try:
        m = os.path.getmtime(KEYS)
    except OSError:
        _state['keys'] = {}
        return _state['keys']
    if m != _state['keys_mtime']:
        try:
            with open(KEYS, encoding='utf-8') as f:
                _state['keys'] = json.load(f)
            _state['keys_mtime'] = m
        except (OSError, ValueError):
            pass
    return _state['keys']


def who_is(auth_header):
    key = (auth_header or '').strip()
    if key.startswith('Bearer '):
        key = key[7:].strip()
    if not key:
        return None
    k = load_keys().get(hash_key(key))
    return k['name'] if k and k.get('active', True) else None


# ---------- checking what friends send ----------
_ISO = re.compile(r'^@\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?(Z|[+-]\d\d:\d\d)?$')   # offset: newer readers
_EXTRA = re.compile(r'^(sold|gone|c\d{1,4}|x?\d{1,4}|#\d{1,4})$', re.I)


def _seen_ok(stamp, now):
    """A row's '@time' is real and not in the future. Rows from older readers have no time zone; their
    local time is at most 14 hours off UTC, so a day of leeway covers every zone."""
    s = stamp[1:].replace('Z', '+00:00')
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.timestamp() <= now + 86400


def clean_line(line, now=None):
    """The line, tidied, if it looks like a MapleReader scan row; otherwise None."""
    if not isinstance(line, str) or len(line) > 300 or '\n' in line or '\r' in line:
        return None
    p = [x.strip() for x in line.split('|')]
    if len(p) < 6 or not p[0] or len(p[0]) > 60 or not p[2] or len(p[2]) > 60:
        return None
    if not re.fullmatch(r'\d{1,10}', p[1].replace(',', '')) or not 1 <= int(p[1].replace(',', '')) <= 2_000_000_000:
        return None
    if not (p[3].isdigit() and 0 <= int(p[3]) <= 40 and p[4].isdigit() and 1 <= int(p[4]) <= 40):
        return None
    extras = p[5:]
    stamps = [x for x in extras if _ISO.match(x)]
    if not stamps:                                    # shared rows must say when they were seen
        return None
    if not all(_seen_ok(x, time.time() if now is None else now) for x in stamps):
        return None
    if not all(_ISO.match(x) or _EXTRA.match(x) for x in extras):
        return None
    if any(ord(c) < 32 for c in line):
        return None
    return ' | '.join(p)


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    server_version = 'MapleMarket'
    timeout = 30                                      # a connection that sends nothing for 30 s is dropped

    def log_message(self, fmt, *a):                  # one short line per request in the service log
        if not os.environ.get('MAPLE_QUIET'):
            sys.stderr.write('%s\n' % (fmt % a))

    def _send(self, code, body, ctype='application/json', cache='no-store'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit):
        """The request's body, or None if it's too big or its size is missing or nonsense."""
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return None
        if not 0 <= n <= limit:
            return None
        return self.rfile.read(n) if n else b''

    # --- reading (anyone with the address) ---
    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ('/', '/index.html'):
            try:
                with open(PAGE, encoding='utf-8') as f:
                    html = f.read()
            except OSError:
                return self._send(500, 'market.html is missing', 'text/plain')
            html = html.replace('<script>', '<script>window.MAPLE={mode:"shared"};</script><script>', 1)
            return self._send(200, html, 'text/html; charset=utf-8')
        if u.path == '/api/ping':
            return self._send(200, {'app': 'MapleMarket'})
        if u.path == '/api/rows':
            try:
                start = max(0, int(parse_qs(u.query).get('from', ['0'])[0]))
            except ValueError:
                start = 0
            return self._send(200, feed(self.server.con, start))
        if u.path == '/api/icons':
            return self._send(200, sorted(f[:-4] for f in os.listdir(ICONS) if f.endswith('.png')) if os.path.isdir(ICONS) else [])
        if u.path.startswith('/icons/') and u.path.endswith('.png'):
            name = os.path.basename(u.path)[:-4]
            if re.fullmatch(r'[a-z0-9-]{1,80}', name):
                try:
                    with open(os.path.join(ICONS, name + '.png'), 'rb') as f:
                        return self._send(200, f.read(), 'image/png', 'public, max-age=3600')
                except OSError:
                    pass
            return self._send(404, 'Not found', 'text/plain')
        if u.path == '/favicon.ico':
            try:
                with open(os.path.join(HERE, 'icon.ico'), 'rb') as f:
                    return self._send(200, f.read(), 'image/x-icon', 'public, max-age=86400')
            except OSError:
                return self._send(404, 'Not found', 'text/plain')
        if u.path == '/robots.txt':
            return self._send(200, 'User-agent: *\nDisallow: /\n', 'text/plain')
        return self._send(404, 'Not found', 'text/plain')

    # --- sending (needs a key) ---
    def do_POST(self):
        u = urlparse(self.path)
        who = who_is(self.headers.get('Authorization'))
        if not who:
            return self._send(401, {'ok': False, 'error': 'Key not accepted. Ask the market owner for a key.'})
        now = time.time()
        bucket, limit = (who, PER_MINUTE) if u.path == '/api/upload' else ((who, 'icons'), ICONS_PER_MINUTE)
        with _rate_lock:
            hits = [t for t in _state['rate'].get(bucket, []) if now - t < 60]
            busy = len(hits) >= limit
            if not busy:
                _state['rate'][bucket] = hits + [now]
        if busy:
            return self._send(429, {'ok': False, 'error': 'Too many uploads; slow down.'})
        if u.path == '/api/upload':
            body = self._body(MAX_BODY)
            if body is None:
                return self._send(413, {'ok': False, 'error': 'Too much at once.'})
            try:
                lines = json.loads(body.decode('utf-8')).get('lines', [])
            except (ValueError, AttributeError):
                return self._send(400, {'ok': False, 'error': 'Not understood.'})
            if not isinstance(lines, list) or len(lines) > MAX_LINES:
                return self._send(400, {'ok': False, 'error': f'Send up to {MAX_LINES} lines at a time.'})
            added, dupes, bad = store(self.server.con, lines, who, now)
            if added or dupes:
                _state['recent'][who] = now
            return self._send(200, {'ok': True, 'added': added, 'dupes': dupes, 'bad': bad, 'who': who})
        if u.path == '/api/icon':
            q = parse_qs(u.query)
            name, kind = q.get('slug', [''])[0], q.get('kind', ['normal'])[0]
            body = self._body(MAX_ICON)
            if not re.fullmatch(r'[a-z0-9-]{1,80}', name) or body is None or not body.startswith(b'\x89PNG\r\n\x1a\n'):
                return self._send(400, {'ok': False, 'error': 'Not a picture.'})
            return self._send(200, {'ok': True, 'kept': keep_icon(name, kind, body)})
        return self._send(404, {'ok': False, 'error': 'Not found'})


def store(con, lines, who, now):
    added = dupes = bad = 0
    with _db_lock:
        for line in lines:
            c = clean_line(line, now)
            if not c:
                bad += 1
                continue
            h = hashlib.sha1(c.encode('utf-8')).hexdigest()
            try:
                con.execute('INSERT INTO rows (h, line, who, at) VALUES (?, ?, ?, ?)', (h, c, who, now))
                added += 1
            except sqlite3.IntegrityError:
                dupes += 1                            # someone already sent exactly this row
        con.commit()
    return added, dupes, bad


def keep_icon(name, kind, png):
    """First picture of an item wins, except a clear one replaces a faded (sold-row) one."""
    os.makedirs(ICONS, exist_ok=True)
    idx_path = os.path.join(ICONS, 'index.json')
    with _db_lock:
        try:
            with open(idx_path, encoding='utf-8') as f:
                idx = json.load(f)
        except (OSError, ValueError):
            idx = {}
        if idx.get(name) == 'normal' or (idx.get(name) == 'faded' and kind != 'normal'):
            return False
        with open(os.path.join(ICONS, name + '.png'), 'wb') as f:
            f.write(png)
        idx[name] = 'normal' if kind == 'normal' else 'faded'
        with open(idx_path, 'w', encoding='utf-8') as f:
            json.dump(idx, f)
        return True


def feed(con, start):
    with _db_lock:
        top = con.execute('SELECT COALESCE(MAX(id), 0) FROM rows').fetchone()[0]
        reset = start > top                           # the database was cleared: start over
        if reset:
            start = 0
        got = con.execute('SELECT id, line FROM rows WHERE id > ? ORDER BY id LIMIT ?', (start, FEED_CHUNK)).fetchall()
    nxt = got[-1][0] if got else start
    now = time.time()
    scanning = sum(1 for t in _state['recent'].values() if now - t < SCANNING_WINDOW)
    return {'text': ''.join(line + '\n' for _, line in got), 'next': nxt, 'more': nxt < top, 'reset': reset,
            'status': {'scanning': scanning, 'total': top}}


class Server(ThreadingHTTPServer):
    daemon_threads = True


def main():
    con = db()
    httpd = Server(('127.0.0.1', PORT), Handler)
    httpd.con = con
    print(f'Maple market listening on 127.0.0.1:{PORT}, data in {DATA}', flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
