"""Serves the market site on your own PC, at http://127.0.0.1:8765, and hands it new scan rows.

The page asks every 2 seconds for whatever was added to scans/all_scans.txt since last time, so
listings show up on the site while you scan, with no importing. Only this PC can reach it: it
listens on 127.0.0.1 and answers only requests addressed to 127.0.0.1 or localhost.

Run on its own (for start.bat users):  py -3.13 -m shopreader.market_server
"""
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import APP_DIR

PORTS = range(8765, 8771)          # the first free one is used; keep it the same so your saved data stays
CHUNK = 2_000_000                  # bytes of all_scans.txt sent per request
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market.html')


def all_scans_path():
    return os.path.join(APP_DIR, 'scans', 'all_scans.txt')


def read_rows(start):
    """(text of complete new lines from byte `start`, next start, more waiting?, file was reset?)"""
    path = all_scans_path()
    try:
        size = os.path.getsize(path)
    except OSError:
        return '', 0, False, start > 0
    reset = start > size                             # the file was deleted or replaced: start over
    if reset:
        start = 0
    with open(path, 'rb') as f:
        f.seek(start)
        data = f.read(CHUNK)
    cut = data.rfind(b'\n')
    if cut < 0:
        return '', start, False, reset               # only a half-written line so far
    data = data[:cut + 1]
    nxt = start + len(data)
    return data.decode('utf-8', 'replace'), nxt, nxt < size, reset


class _Handler(BaseHTTPRequestHandler):
    server_version = 'MapleReader'

    def log_message(self, *a):                       # stay quiet (the app has no console)
        pass

    def _send(self, code, body, ctype, cache='no-store'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', cache)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _local(self):
        port = self.server.server_address[1]
        return self.headers.get('Host', '') in (f'127.0.0.1:{port}', f'localhost:{port}')

    def _json(self, obj, code=200):
        return self._send(code, json.dumps(obj), 'application/json')

    def do_POST(self):
        """Button presses from the app window. They must carry the X-MapleReader header, which other
        websites can't add to a request to this PC, so a web page elsewhere can't press buttons."""
        c = self.server.controller
        if not self._local() or self.headers.get('X-MapleReader') != '1' or c is None:
            return self._send(403, 'Forbidden', 'text/plain')
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            n = -1
        if n < 0:
            return self._json({'ok': False, 'error': 'Bad request.'}, 400)
        if n > 30_000_000:
            return self._json({'ok': False, 'error': 'Too big.'}, 413)
        body = self.rfile.read(n) if n else b''
        path = urlparse(self.path).path
        try:
            if path == '/api/picture':
                return self._json(c.read_picture(body))
            d = json.loads(body.decode('utf-8') or '{}') if body else {}
            act = {'/api/start': lambda: c.start(d.get('channel', 0)), '/api/stop': c.stop,
                   '/api/set': lambda: c.update(d), '/api/open-scans': c.open_scans,
                   '/api/install-tesseract': c.install_tesseract, '/api/update': c.install_update,
                   '/api/update-check': lambda: c.check_update(wait=True), '/api/exp-reset': c.exp_reset,
                   '/api/exp-log': lambda: c.exp_log_edit(d), '/api/mob-name': lambda: c.mob_name(d)}.get(path)
            if not act:
                return self._send(404, 'Not found', 'text/plain')
            return self._json(act())
        except (ValueError, TypeError) as e:
            return self._json({'ok': False, 'error': f'Bad value: {e}'}, 400)
        except Exception as e:
            return self._json({'ok': False, 'error': f'{type(e).__name__}: {e}'}, 500)

    def do_GET(self):
        if not self._local():
            return self._send(403, 'Forbidden', 'text/plain')    # blocks other websites pretending to be local
        u = urlparse(self.path)
        c = self.server.controller
        if u.path == '/api/state' and c is not None:
            try:
                since = int(parse_qs(u.query).get('since', ['0'])[0])
            except ValueError:
                since = 0
            return self._json(c.snapshot(since))
        if u.path.startswith('/icons/') and u.path.endswith('.png'):
            name = os.path.basename(u.path)[:-4]
            if not name.replace('-', '').isalnum():
                return self._send(404, 'Not found', 'text/plain')
            try:
                with open(os.path.join(APP_DIR, 'scans', 'icons', name + '.png'), 'rb') as f:
                    return self._send(200, f.read(), 'image/png', 'max-age=600')
            except OSError:
                pass
            return self._send(404, 'Not found', 'text/plain')
        if u.path.startswith('/api/mobpic/') and u.path.endswith('.png') and c is not None:
            name = os.path.basename(u.path)[:-4]
            if name.isascii() and name.isdigit():    # '²' is a digit too, but int() refuses it
                try:
                    with open(c.mobpics.path(int(name)), 'rb') as f:
                        return self._send(200, f.read(), 'image/png', 'max-age=60')
                except OSError:
                    pass
            return self._send(404, 'Not found', 'text/plain')
        if u.path == '/favicon.ico':
            try:
                with open(os.path.join(os.path.dirname(PAGE), 'icon.ico'), 'rb') as f:
                    return self._send(200, f.read(), 'image/x-icon')
            except OSError:
                return self._send(404, 'Not found', 'text/plain')
        if u.path == '/api/icons':
            from .icons import known
            return self._json(sorted(known()))
        if u.path in ('/', '/index.html'):
            try:
                with open(PAGE, 'rb') as f:
                    return self._send(200, f.read(), 'text/html; charset=utf-8')
            except OSError:
                return self._send(500, 'market.html is missing next to market_server.py', 'text/plain')
        if u.path == '/api/ping':
            return self._send(200, json.dumps({'app': 'MapleReader'}), 'application/json')
        if u.path == '/api/rows':
            try:
                start = max(0, int(parse_qs(u.query).get('from', ['0'])[0]))
            except ValueError:
                start = 0
            text, nxt, more, reset = read_rows(start)
            status = self.server.status_fn() if self.server.status_fn else None
            if c is not None:
                status = dict(c.status_line(), app=True)
            return self._send(200, json.dumps({'text': text, 'next': nxt, 'more': more, 'reset': reset,
                                               'status': status}), 'application/json')
        return self._send(404, 'Not found', 'text/plain')


class _Server(ThreadingHTTPServer):
    # On Windows "reuse address" would let a second copy grab the same port; don't allow that.
    allow_reuse_address = sys.platform != 'win32'
    daemon_threads = True


class MarketServer:
    """Start it once; it runs in the background until the program closes."""
    def __init__(self, status_fn=None, controller=None, ports=PORTS):
        self.status_fn, self.controller, self.ports = status_fn, controller, ports
        self.httpd, self.url, self.shared = None, None, False

    def start(self):
        for port in self.ports:
            try:
                httpd = _Server(('127.0.0.1', port), _Handler)
            except OSError:
                if _is_ours(port):                   # another MapleReader already serves it: use that one
                    self.url, self.shared = f'http://127.0.0.1:{port}/', True
                    return self.url
                continue
            httpd.status_fn, httpd.controller = self.status_fn, self.controller
            self.httpd, self.url = httpd, f'http://127.0.0.1:{port}/'
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            return self.url
        return None

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


def _is_ours(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/ping', timeout=1) as r:
            return json.loads(r.read().decode()).get('app') == 'MapleReader'
    except Exception:
        return False


if __name__ == '__main__':
    import webbrowser
    os.chdir(APP_DIR)
    s = MarketServer()
    url = s.start()
    if not url:
        print('Could not start the market: ports 8765-8770 are all in use.')
    else:
        print('Market running at', url, ' (close this window to stop it)')
        print('New rows in', all_scans_path(), 'appear on the page by themselves.')
        webbrowser.open(url)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
