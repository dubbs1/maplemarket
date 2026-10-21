"""Maple Classic Market on Vercel + Supabase: the group's shared market (maple.vendormarket.app).

The same addresses as maple-server/server.py, so MapleReader's uploader (share.py) and the market page work
unchanged: GET /api/ping, /api/rows?from=N, /api/icons, /icons/<slug>.png; POST /api/upload, /api/icon (with
a personal key). vercel.json sends /api/* and /icons/* here. Listings, keys and the picture index live in
Supabase (schema.sql), reached through its maple_* functions with the secret key; the pictures are in Supabase
Storage (bucket "icons"). Plain Python, no add-ons.

Settings (Vercel > the project > Settings > Environment Variables):
  SUPABASE_URL          https://<your project>.supabase.co
  SUPABASE_SECRET_KEY   the secret key (sb_secret_...), or the older service_role key (SUPABASE_SERVICE_KEY)
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlparse

MAX_BODY = 2_000_000              # bytes per upload
MAX_LINES = 5000                  # lines per upload
MAX_ICON = 100_000                # bytes per picture
PER_MINUTE = 60                   # row uploads per key per minute (per running copy of this program)
ICONS_PER_MINUTE = 300            # picture uploads per key per minute (a first share sends many)
FEED_CHUNK = 5000                 # lines per /api/rows answer
TIMEOUT = 20                      # seconds to wait for Supabase

_rate = {}


def _config():
    url = (os.environ.get('SUPABASE_URL') or '').strip().rstrip('/')
    key = (os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or '').strip()
    return url, key


class Down(Exception):
    """Supabase isn't answering (or isn't set up yet)."""


def _supabase(path, body=None, ctype='application/json', extra=None):
    url, key = _config()
    if not url or not key:
        raise Down('This market is not set up yet: SUPABASE_URL and SUPABASE_SECRET_KEY are missing in Vercel.')
    h = {'apikey': key, 'Content-Type': ctype}
    if not key.startswith('sb_'):                     # (the older keys go in Authorization too; the new ones must not)
        h['Authorization'] = 'Bearer ' + key
    h.update(extra or {})
    req = urllib.request.Request(url + path, data=body, headers=h, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode('utf-8', 'replace')
        sys.stderr.write(f'supabase {path}: {e.code} {detail}\n')
        raise Down(f'The market\'s database said no ({e.code}). If you run this market, check schema.sql was run.')
    except (urllib.error.URLError, OSError) as e:
        raise Down(f'The market\'s database is not answering ({e}). Try again in a minute.')


def rpc(fn, **args):
    return json.loads(_supabase('/rest/v1/rpc/' + fn, json.dumps(args).encode('utf-8')) or b'null')


def hash_key(key):
    return hashlib.sha256(key.strip().encode('utf-8')).hexdigest()


def who_is(auth_header):
    key = (auth_header or '').strip()
    if key.startswith('Bearer '):
        key = key[7:].strip()
    if not re.fullmatch(r'mm-[0-9a-f]{32}', key):   # (every key is shaped like this: anything else is refused for free)
        return None
    return rpc('maple_who', p_hash=hash_key(key))


# ---------- checking what friends send (the same rules as maple-server/server.py) ----------
# re.ASCII: digits are 0-9 only ("²" or Arabic-Indic digits are not numbers here)
_ISO = re.compile(r'^@\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?(Z|[+-]\d\d:\d\d)?$', re.ASCII)   # offset: newer readers
_EXTRA = re.compile(r'^(sold|gone|c\d{1,4}|x?\d{1,4}|#\d{1,4})$', re.I | re.ASCII)
_NUM = re.compile(r'[0-9]{1,10}')


def _seen_ok(stamp, now):
    """A row's '@time' is real, not in the future and not older than the 35 days kept (a friend's first share
    sends their whole history: nobody needs the old part). Rows from older readers have no time zone; their
    local time is at most 14 hours off UTC, so a day of leeway covers every zone."""
    s = stamp[1:].replace('Z', '+00:00')
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return now - 35 * 86400 <= t.timestamp() <= now + 86400


def clean_line(line, now=None):
    """The line, tidied, if it looks like a MapleReader scan row; otherwise None."""
    if not isinstance(line, str) or len(line) > 300 or '\n' in line or '\r' in line:
        return None
    p = [x.strip() for x in line.split('|')]
    if len(p) < 6 or not p[0] or len(p[0]) > 60 or not p[2] or len(p[2]) > 60:
        return None
    if not _NUM.fullmatch(p[1].replace(',', '')) or not 1 <= int(p[1].replace(',', '')) <= 2_000_000_000:
        return None
    if not (_NUM.fullmatch(p[3]) and 0 <= int(p[3]) <= 40 and _NUM.fullmatch(p[4]) and 1 <= int(p[4]) <= 40):
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
class handler(BaseHTTPRequestHandler):               # (Vercel looks for a class called "handler")
    server_version = 'MapleMarket'

    def log_message(self, fmt, *a):
        if not os.environ.get('MAPLE_QUIET'):
            sys.stderr.write('%s\n' % (fmt % a))

    def _send(self, code, body, ctype='application/json', cache='no-store', extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
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

    def _route(self):
        """Which address was asked for: vercel.json passes it as ?route=, or it's in the path itself."""
        u = urlparse(self.path)
        q = parse_qs(u.query)
        r = q.get('route', [''])[0]
        if not r:
            path = u.path.rstrip('/')
            if path.startswith('/icons/'):
                r, q['file'] = 'iconfile', [path[len('/icons/'):]]
            else:
                r = path.rsplit('/', 1)[-1]
        return r, q

    # --- reading (anyone with the address) ---
    def do_GET(self):
        r, q = self._route()
        try:
            if r == 'ping':
                return self._send(200, {'app': 'MapleMarket'})
            if r == 'rows':
                try:
                    start = min(max(0, int(q.get('from', ['0'])[0])), 2 ** 62)   # (a bigint, so Postgres never says no)
                except ValueError:
                    start = 0
                # pages ask every 20 s; a few seconds at Vercel's edge lets friends looking at once share one answer
                return self._send(200, rpc('maple_feed', p_start=start, p_now=time.time(), p_lim=FEED_CHUNK),
                                  cache='public, s-maxage=5, stale-while-revalidate=30')
            if r == 'icons':
                return self._send(200, rpc('maple_icon_list') or [], cache='public, max-age=60')
            if r == 'iconfile':
                name = q.get('file', [''])[0]
                name = name[:-4] if name.endswith('.png') else ''
                url, _ = _config()
                if not re.fullmatch(r'[a-z0-9-]{1,80}', name) or not url:
                    return self._send(404, 'Not found', 'text/plain')
                # the pictures are public in Supabase Storage: send the browser there (cached for an hour)
                return self._send(302, '', 'text/plain', 'public, max-age=3600',
                                  {'Location': f'{url}/storage/v1/object/public/icons/{quote(name)}.png'})
        except Down as e:
            return self._send(503, {'ok': False, 'error': str(e)})
        return self._send(404, 'Not found', 'text/plain')

    # --- sending (needs a key) ---
    def do_POST(self):
        r, q = self._route()
        if r not in ('upload', 'icon'):
            return self._send(404, {'ok': False, 'error': 'Not found'})
        try:
            who = who_is(self.headers.get('Authorization'))
            if not who:
                return self._send(401, {'ok': False, 'error': 'Key not accepted. Ask the market owner for a key.'})
            now = time.time()
            bucket, limit = (who, PER_MINUTE) if r == 'upload' else ((who, 'icons'), ICONS_PER_MINUTE)
            hits = [t for t in _rate.get(bucket, []) if now - t < 60]
            if len(hits) >= limit:
                return self._send(429, {'ok': False, 'error': 'Too many uploads; slow down.'})
            _rate[bucket] = hits + [now]
            if r == 'upload':
                body = self._body(MAX_BODY)
                if body is None:
                    return self._send(413, {'ok': False, 'error': 'Too much at once.'})
                try:
                    lines = json.loads(body.decode('utf-8')).get('lines', [])
                except (ValueError, AttributeError):
                    return self._send(400, {'ok': False, 'error': 'Not understood.'})
                if not isinstance(lines, list) or len(lines) > MAX_LINES:
                    return self._send(400, {'ok': False, 'error': f'Send up to {MAX_LINES} lines at a time.'})
                good = []
                for line in lines:
                    try:
                        c = clean_line(line, now)
                    except (ValueError, TypeError):
                        c = None                      # never let one odd line stop the rest
                    if c:
                        good.append(c)
                got = rpc('maple_store', p_who=who, p_lines=good, p_now=now) if good else {'added': 0, 'dupes': 0}
                return self._send(200, {'ok': True, 'added': got['added'], 'dupes': got['dupes'], 'bad': len(lines) - len(good),
                                        'who': who})
            name, kind = q.get('slug', [''])[0], q.get('kind', ['normal'])[0]
            body = self._body(MAX_ICON)
            if not re.fullmatch(r'[a-z0-9-]{1,80}', name) or body is None or not body.startswith(b'\x89PNG\r\n\x1a\n'):
                return self._send(400, {'ok': False, 'error': 'Not a picture.'})
            if not rpc('maple_icon_ok', p_slug=name, p_kind=kind):
                return self._send(200, {'ok': True, 'kept': False})
            _supabase(f'/storage/v1/object/icons/{name}.png', body, 'image/png', {'x-upsert': 'true', 'Cache-Control': 'max-age=3600'})
            rpc('maple_icon_set', p_slug=name, p_kind=kind)   # (listed only once the picture is really there)
            return self._send(200, {'ok': True, 'kept': True})
        except Down as e:
            return self._send(503, {'ok': False, 'error': str(e)})
