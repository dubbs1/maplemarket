"""Serves the app's page on your own PC, at http://127.0.0.1:8765, and answers the window's requests.

Only this PC can reach it: it listens on 127.0.0.1 and answers only requests addressed to 127.0.0.1 or
localhost. Button presses (POST) must carry the X-MapleReader header, which other websites can't add.
"""
import json
import os
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORTS = range(8765, 8771)          # the first free one is used
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.html')


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
        """Button presses from the app window."""
        c = self.server.controller
        if not self._local() or self.headers.get('X-MapleReader') != '1' or c is None:
            return self._send(403, 'Forbidden', 'text/plain')
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            n = -1
        if n < 0:
            return self._json({'ok': False, 'error': 'Bad request.'}, 400)
        if n > 1_000_000:
            return self._json({'ok': False, 'error': 'Too big.'}, 413)
        body = self.rfile.read(n) if n else b''
        path = urlparse(self.path).path
        try:
            d = json.loads(body.decode('utf-8') or '{}') if body else {}
            act = {'/api/set': lambda: c.update(d), '/api/open-scans': c.open_scans,
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
        if u.path in ('/', '/index.html'):
            try:
                with open(PAGE, 'rb') as f:
                    return self._send(200, f.read(), 'text/html; charset=utf-8')
            except OSError:
                return self._send(500, 'app.html is missing next to server.py', 'text/plain')
        if u.path == '/api/ping':
            return self._send(200, json.dumps({'app': 'MapleReader'}), 'application/json')
        return self._send(404, 'Not found', 'text/plain')


class _Server(ThreadingHTTPServer):
    # On Windows "reuse address" would let a second copy grab the same port; don't allow that.
    allow_reuse_address = sys.platform != 'win32'
    daemon_threads = True


class AppServer:
    """Start it once; it runs in the background until the program closes."""
    def __init__(self, controller=None, ports=PORTS):
        self.controller, self.ports = controller, ports
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
            httpd.controller = self.controller
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
