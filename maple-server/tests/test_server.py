"""Checks for the shared market server. Run:  python3 tests/test_server.py"""
import json, os, subprocess, sys, tempfile, threading, time, urllib.error, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DATA = tempfile.mkdtemp(prefix='maple_srv_'); os.environ['MAPLE_DATA'] = DATA; os.environ['MAPLE_PORT'] = '8799'; os.environ['MAPLE_QUIET'] = '1'
sys.path.insert(0, ROOT)
import server as S  # noqa: E402

fails = []
def ok(n, c):
    print(('ok     ' if c else 'FAILED ') + n)
    if not c: fails.append(n)

def call(path, data=None, key=None, ctype='application/json', method=None):
    h = {'Content-Type': ctype}
    if key: h['Authorization'] = 'Bearer ' + key
    req = urllib.request.Request('http://127.0.0.1:8799' + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read()
            return r.status, (json.loads(body) if r.headers.get('Content-Type', '').startswith('application/json') else body)
    except urllib.error.HTTPError as e:
        b = e.read()
        try: b = json.loads(b)
        except Exception: pass
        return e.code, b

def manage(*args):
    return subprocess.run([sys.executable, os.path.join(ROOT, 'manage.py'), *args], capture_output=True, text=True,
                          env=dict(os.environ)).stdout

def main():
    httpd = S.Server(('127.0.0.1', 8799), S.Handler); httpd.con = S.db()
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    k1 = manage('add', 'Cass').split('Key for Cass:')[1].split()[0]
    k2 = manage('add', 'Gunther').split('Key for Gunther:')[1].split()[0]
    ok('keys made for two friends', k1.startswith('mm-') and k2.startswith('mm-') and k1 != k2)
    ok('a second key for the same name is refused', 'already has a key' in manage('add', 'cass'))
    code, page = call('/')
    ok('the page is served in shared mode', code == 200 and b'window.MAPLE={mode:"shared"}' in page)
    up = lambda key, lines: call('/api/upload', json.dumps({'lines': lines}).encode(), key)
    L = ['Bunny Ears | 62999 | Cheapest NX <3 | 1 | 10 | c1 | @2026-10-19T15:31:08',
         'Bunny Ears | 62999 | Cheapest NX <3 | 1 | 10 | c2 | @2026-10-19T15:31:08',
         'Red Sailor Shirt | 19999 | Tell me | 1 | 10 | sold | c1 | @2026-10-19T15:32:00']
    ok('no key: refused', up(None, L)[0] == 401)
    ok('wrong key: refused', up('mm-nope', L)[0] == 401)
    code, r = up(k1, L + ['junk', 'A | 5 | B | 1 | 99 | @2026-10-19T15:31:08', 'No time | 5 | Shop | 1 | 3', 'Evil | 5 | <script> | 1 | 3 | <b> | @2026-10-19T15:31:08'])
    ok(f'good rows kept, bad ones dropped ({r})', code == 200 and r['added'] == 3 and r['bad'] == 4)
    code, r = up(k2, L[:2] + ['Ice Wand | 12500 | WCC | 2 | 10 | c1 | @2026-10-19T15:40:00'])
    ok(f"the same rows from a friend aren't stored twice ({r})", r['added'] == 1 and r['dupes'] == 2)
    future = time.strftime('@%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() + 3 * 86400))
    code, r = up(k1, ['Zone Item | 700 | East Shop | 2 | 5 | c1 | @2026-10-19T15:41:00-04:00',
                      'Zone Item | 700 | UTC Shop | 2 | 5 | c1 | @2026-10-19T19:41:00Z',
                      f'Future Item | 700 | Shop | 2 | 5 | c1 | {future}'])
    ok(f'times with a time zone are kept; times in the future are refused ({r})', r['added'] == 2 and r['bad'] == 1)
    code, f = call('/api/rows?from=0')
    ok('everyone can read the rows', code == 200 and f['text'].count('\n') == 6 and f['status']['scanning'] == 2)
    code, f2 = call(f"/api/rows?from={f['next']}")
    ok('reading again gives nothing new', f2['text'] == '' and not f2['reset'])
    png = open(os.path.join(ROOT, 'tests', 'pic.png'), 'rb').read() if os.path.exists(os.path.join(ROOT, 'tests', 'pic.png')) else None
    if png is None:
        from PIL import Image; import io
        b = io.BytesIO(); Image.new('RGB', (40, 40), (200, 50, 50)).save(b, 'PNG'); png = b.getvalue()
    ok('a picture needs a key', call('/api/icon?slug=bunny-ears&kind=normal', png, None, 'image/png')[0] == 401)
    code, r = call('/api/icon?slug=bunny-ears&kind=faded', png, k1, 'image/png')
    ok('a picture is kept', code == 200 and r['kept'])
    code, r = call('/api/icon?slug=bunny-ears&kind=normal', png, k2, 'image/png')
    ok('a clear picture replaces a faded one', r['kept'])
    code, r = call('/api/icon?slug=bunny-ears&kind=normal', png, k1, 'image/png')
    ok('then it is kept as is', not r['kept'])
    ok('not-a-picture refused', call('/api/icon?slug=x&kind=normal', b'hello', k1, 'image/png')[0] == 400)
    ok('bad picture name refused', call('/api/icon?slug=../../etc&kind=normal', png, k1, 'image/png')[0] == 400)
    code, body = call('/icons/bunny-ears.png')
    ok('pictures can be viewed', code == 200 and body[:4] == b'\x89PNG')
    ok('pictures list', call('/api/icons')[1] == ['bunny-ears'])
    manage('revoke', 'Gunther')
    ok('a revoked key stops working at once', up(k2, L)[0] == 401)
    manage('restore', 'Gunther')
    ok('restored, it works again', up(k2, L)[0] == 200)
    out = manage('purge', 'Gunther')
    code, f = call('/api/rows?from=0')
    ok(f'purge deletes what someone sent ({out.strip()})', 'Deleted 1' in out and f['text'].count('\n') == 5)
    manage('revoke', 'Gunther')
    out = manage('add', 'Gunther')
    k3 = out.split('Key for Gunther:')[1].split()[0] if 'Key for Gunther:' in out else ''
    ok('after a revoke, the same person can get a new key', k3.startswith('mm-') and up(k3, [])[0] == 200)
    ok('the old key stays revoked', 'stay revoked' in manage('restore', 'Gunther') and up(k2, [])[0] == 401)
    import socket
    sk = socket.create_connection(('127.0.0.1', 8799), timeout=5)
    sk.sendall(f'POST /api/upload HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer {k1}\r\nContent-Length: -1\r\n\r\n'.encode())
    answer = sk.recv(200); sk.close()
    ok('a nonsense Content-Length is refused straight away (no waiting)', b' 413 ' in answer or b' 400 ' in answer)
    many = [f'Item {i} | {100 + i} | Shop | 3 | 4 | c1 | @2026-10-19T16:{i // 60 % 60:02d}:{i % 60:02d}' for i in range(5000)]
    code, r = up(k1, many)
    ok(f'5,000 rows in one go ({r.get("added")})', code == 200 and r['added'] == 5000)
    code, f = call('/api/rows?from=0')
    ok('the feed comes in pieces', f['more'] and f['text'].count('\n') == 5000)
    hits = [up(k1, [])[0] for _ in range(70)]
    ok('too many uploads in a minute are slowed down', 429 in hits)
    print('SERVER CHECK PASSED' if not fails else f'{len(fails)} SERVER CHECK(S) FAILED')
    httpd.shutdown()
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
