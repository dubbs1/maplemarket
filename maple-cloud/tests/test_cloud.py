"""Checks the group market's Vercel + Supabase version (maple-cloud/) for real, on this machine:
a throwaway Postgres holds schema.sql (loaded twice: running it again must be safe), a small stand-in answers like
Supabase (its rpc and Storage addresses, run as Supabase's service_role), and api/market.py serves in front of it,
as Vercel would. MapleReader's own uploader and reader (share.py) talk to it.

Needs Postgres's programs (initdb, pg_ctl, postgres, psql: on Ubuntu, package postgresql).
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'maple-cloud', 'api'))
sys.path.insert(0, os.path.join(ROOT, 'maple-server'))
sys.path.insert(0, os.path.join(ROOT, 'MapleReader'))
os.environ['MAPLE_QUIET'] = '1'
import market as C                                          # noqa: E402
import server as OLD                                        # noqa: E402
from shopreader import share                                # noqa: E402

fails = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        fails.append(what)


# ---------- a throwaway Postgres ----------
def pg_bin(name):
    found = shutil.which(name) if name == 'psql' else None
    return found or (sorted(glob.glob(f'/usr/lib/postgresql/*/bin/{name}')) or [None])[-1]


AS_PG = ['runuser', '-u', 'postgres', '--'] if os.geteuid() == 0 else []   # (Postgres won't run as root)


class PG:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix='maple_pg_')
        if AS_PG:
            shutil.chown(self.dir, 'postgres')
        subprocess.run(AS_PG + [pg_bin('initdb'), '-D', self.dir + '/data', '-A', 'trust', '-U', 'postgres'], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run(AS_PG + [pg_bin('pg_ctl'), '-D', self.dir + '/data', '-o', f"-k {self.dir} -h ''", '-l', self.dir + '/log',
                                '-w', 'start'], check=True, stdout=subprocess.DEVNULL)
        self.types = {}

    def sql(self, text, role=None, **var):
        """Run SQL (with psql's :'name' variables); returns the output, or raises with Postgres's message."""
        args = [pg_bin('psql'), '-h', self.dir, '-U', 'postgres', '-X', '-q', '-At', '-v', 'ON_ERROR_STOP=1']
        for k, v in var.items():
            args += ['-v', f'{k}={v}']
        r = subprocess.run(args, input=(f'set role {role};\n' if role else '') + text, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stderr.strip())
        return r.stdout.strip()

    def call(self, fn, args):
        """Like Supabase's /rest/v1/rpc/<fn>: named arguments in, the function's value out as JSON."""
        if fn not in self.types:
            out = self.sql("select string_agg(n || ' ' || format_type(t, null), ',') from pg_proc, "
                           "unnest(proargnames, proargtypes::oid[]) as a(n, t) where proname = :'f'", f=fn)
            self.types[fn] = dict(x.split(' ', 1) for x in out.split(',')) if out else {}
        T = self.types[fn]
        parts = []
        for k, v in args.items():                         # (big values go in the script itself, dollar-quoted)
            v = json.dumps(v) if T[k] == 'json' else str(v)
            tag = '$v%d$' % next(i for i in range(10 ** 6) if '$v%d$' % i not in v)
            parts.append(f"{k} => ({tag}{v}{tag})::{T[k]}")
        return self.sql(f"select coalesce(to_json({fn}({', '.join(parts)}))::text, 'null');", role='service_role')

    def stop(self):
        subprocess.run(AS_PG + [pg_bin('pg_ctl'), '-D', self.dir + '/data', '-m', 'immediate', 'stop'], stdout=subprocess.DEVNULL)
        shutil.rmtree(self.dir, ignore_errors=True)


# ---------- a stand-in for Supabase ----------
SECRET = 'sb_secret_test_only'
STORE = {}


def fake_supabase(pg):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype='application/json'):
            body = body if isinstance(body, bytes) else body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.headers.get('apikey') != SECRET or 'Authorization' in self.headers:
                return self._send(401, '{"message":"Invalid API key"}')
            body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
            if self.path.startswith('/rest/v1/rpc/'):
                try:
                    return self._send(200, pg.call(self.path.rsplit('/', 1)[-1], json.loads(body or b'{}')))
                except RuntimeError as e:
                    return self._send(400, json.dumps({'message': str(e)}))
            if self.path.startswith('/storage/v1/object/icons/'):
                name = self.path.rsplit('/', 1)[-1]
                if name in STORE and self.headers.get('x-upsert') != 'true':
                    return self._send(400, '{"message":"The resource already exists"}')
                STORE[name] = body
                return self._send(200, '{"Key":"icons/' + name + '"}')
            return self._send(404, '{}')

        def do_GET(self):
            name = self.path.rsplit('/', 1)[-1]
            if self.path.startswith('/storage/v1/object/public/icons/') and name in STORE:
                return self._send(200, STORE[name], 'image/png')
            return self._send(404, '{}')
    s = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def serve_market():
    s = ThreadingHTTPServer(('127.0.0.1', 0), C.handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f'http://127.0.0.1:{s.server_address[1]}'


def http(url, body=None, key=None, ctype='application/json', follow=True):
    h = {'Content-Type': ctype}
    if key:
        h['Authorization'] = 'Bearer ' + key
    req = urllib.request.Request(url, data=body, headers=h, method='POST' if body is not None else 'GET')
    opener = urllib.request.build_opener(*([] if follow else [NoRedirect()]))
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def stamp(ago=0):
    return time.strftime('@%Y-%m-%dT%H:%M:%S', time.localtime(time.time() - ago)) + time.strftime('%z')[:3] + ':' + time.strftime('%z')[3:]


def main():
    print('The group market on Vercel + Supabase:')
    pg = PG()
    try:
        # Supabase's roles: the website's service_role skips row level security; the public ones don't
        pg.sql('create role anon; create role authenticated; create role service_role bypassrls;')
        schema = os.path.join(ROOT, 'maple-cloud', 'schema.sql')
        for _ in range(2):
            pg.sql(open(schema, encoding='utf-8').read())
            pg.sql('grant all on all tables in schema public to service_role; grant all on all sequences in schema public to service_role;')
        check(True, 'schema.sql runs, and runs again safely')
        for role, q in (('anon', 'select maple_feed(0, 1, 10)'), ('anon', 'select * from maple_rows'),
                        ('authenticated', 'select * from maple_people'), ('service_role', "select maple_add_key('X')")):
            try:
                pg.sql(q, role=role)
                check(False, f'{role} must not run: {q}')
            except RuntimeError as e:
                check('permission denied' in str(e), f'{role} cannot: {q}')
        key = pg.sql("select maple_add_key('Gunther');")
        check(key.startswith('mm-') and len(key) == 35, f'select maple_add_key(...) makes a key ({key[:6]}...)')
        try:
            pg.sql("select maple_add_key('gunther');")
            check(False, 'a second working key for the same name is refused')
        except RuntimeError as e:
            check('already has a key' in str(e), 'a second working key for the same name is refused')

        sb = fake_supabase(pg)
        os.environ['SUPABASE_URL'] = f'http://127.0.0.1:{sb.server_address[1]}'
        os.environ['SUPABASE_SECRET_KEY'] = SECRET
        web, url = serve_market()

        code, body, _ = http(url + '/api/ping')
        check(code == 200 and json.loads(body)['app'] == 'MapleMarket', '/api/ping answers')
        rows = [f'Ilbi Throwing-Stars | 2,350,000 | Lucky Stars | 3 | 5 | c1 | {stamp(60)}',
                f'Power Elixir | 8000 | Cheap Pots | 1 | 2 | c1 | {stamp(30)}']
        up = json.dumps({'lines': rows + [rows[0], 'not a row', f'Future | 5 | S | 1 | 2 | {stamp(-3 * 86400)}']}).encode()
        code, body, _ = http(url + '/api/upload', up)
        check(code == 401, 'sending without a key is refused')
        code, body, _ = http(url + '/api/upload', up, key='mm-wrong')
        check(code == 401, 'a wrong key is refused')
        code, body, _ = http(url + '/api/upload', up, key=key)
        got = json.loads(body)
        check(code == 200 and (got['added'], got['dupes'], got['bad'], got['who']) == (2, 1, 2, 'Gunther'),
              f'upload: 2 added, 1 already there, 2 bad lines refused, from Gunther ({got})')
        code, body, _ = http(url + '/api/rows?from=0')
        feed = json.loads(body)
        check(code == 200 and feed['text'].splitlines() == [OLD.clean_line(r) for r in rows] and feed['status']['scanning'] == 1
              and not feed['more'], f'/api/rows: both rows, tidied, "1 scanning now" (next {feed["next"]})')
        code, body, _ = http(url + f'/api/market?route=rows&from={feed["next"]}')
        check(json.loads(body)['text'] == '', 'the address as vercel.json passes it (?route=rows) works too, and from=next is empty')
        code, body, _ = http(url + '/api/rows?from=99999')
        check(json.loads(body)['reset'] is True, 'a page ahead of the database (it was cleared) is told to start over')
        many = [f'Bulk {i} | {100 + i} | Shop | 1 | 2 | c1 | {stamp(10)}' for i in range(5200)]
        for i in range(0, len(many), 5000):
            http(url + '/api/upload', json.dumps({'lines': many[i:i + 5000]}).encode(), key=key)
        first = share.fetch_rows(url, 0)
        rest = share.fetch_rows(url, first['next'])
        check(first['more'] and len(first['text'].splitlines()) == 5000 and len(rest['text'].splitlines()) == 202 and not rest['more'],
              'a big market comes in pages of 5,000 (MapleReader\'s own reader)')

        png = b'\x89PNG\r\n\x1a\n' + b'x' * 50
        res = [json.loads(http(url + f'/api/icon?slug=ilbi&kind={k}', p, key=key, ctype='image/png')[1]).get('kept')
               for k, p in (('faded', png + b'1'), ('faded', png + b'2'), ('normal', png + b'3'), ('normal', png + b'4'))]
        check(res == [True, False, True, False], f'pictures: the first is kept, a clear one replaces a faded one, never the other way ({res})')
        code, body, _ = http(url + '/api/icon?slug=bad&kind=normal', b'GIF89a', key=key, ctype='image/png')
        check(code == 400, 'something that is not a PNG is refused')
        code, body, _ = http(url + '/api/icons')
        check(json.loads(body) == ['ilbi'], '/api/icons lists the pictures')
        code, body, hd = http(url + '/icons/ilbi.png', follow=False)
        check(code == 302 and hd['Location'].endswith('/storage/v1/object/public/icons/ilbi.png'), '/icons/<item>.png sends the browser to Storage')
        check(share.fetch_icon(url, 'ilbi') == png + b'3', 'and the picture is the clear one (MapleReader\'s own reader)')
        check(http(url + '/icons/..%2Fsecret.png', follow=False)[0] == 404, 'odd picture names are refused')

        print('  ' + pg.sql("select maple_revoke('Gunther');"))
        code, body, _ = http(url + '/api/upload', up, key=key)
        check(code == 401, 'a revoked key no longer works')
        pg.sql("select maple_restore('Gunther');")
        check(http(url + '/api/upload', up, key=key)[0] == 200, 'restored, it works again')
        out = pg.sql("select maple_purge('Gunther');")
        check(out.startswith('Deleted 5202 listings'), f'maple_purge deletes what they sent ({out[:30]}...)')

        sb.shutdown()
        sb.server_close()
        code, body, _ = http(url + '/api/rows?from=0')
        check(code == 503 and 'not answering' in json.loads(body)['error'], 'Supabase down: a clear message, no crash')
        del os.environ['SUPABASE_SECRET_KEY']
        code, body, _ = http(url + '/api/rows?from=0')
        check(code == 503 and 'not set up yet' in json.loads(body)['error'], 'settings missing in Vercel: it says which')
        web.shutdown()

        corpus = rows + ['x | 1 | s | 0 | 1 | @2026-01-01T00:00', 'x | ² | s | 1 | 1 | @2026-01-01T00:00', 'x | 1 | s | 41 | 1 | @2026-01-01T00:00',
                         'x | 1 | s | 1 | 1 | c1', 'x | 1 | s | 1 | 1 | sold | @2026-01-01T00:00:00Z', 'x | 1 | s | 1 | 1 | hack | @2026-01-01T00:00',
                         '\x01 | 1 | s | 1 | 1 | @2026-01-01T00:00', 'a' * 61 + ' | 1 | s | 1 | 1 | @2026-01-01T00:00', None, 5]
        check(all(C.clean_line(x) == OLD.clean_line(x) for x in corpus), 'the same rules as the droplet server for what is accepted')
    finally:
        pg.stop()
    print()
    print('GROUP MARKET (CLOUD): all checks passed.' if not fails else f'GROUP MARKET (CLOUD): {len(fails)} FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    if not pg_bin('initdb'):
        sys.exit('Postgres is not installed (initdb not found): on Ubuntu, sudo apt install postgresql')
    sys.exit(main())
