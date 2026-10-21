"""A pretend group market for the browser checks: the real Vercel function (maple-cloud/api/market.py) in front of a
throwaway Postgres with schema.sql and a stand-in for Supabase (both from maple-cloud/tests/test_cloud.py), plus the
page itself at /, as Vercel serves it.

    python3 cloud_stub.py <port> <name> [<name>...]

It prints one JSON line with a key per name, then waits for a line on stdin before it starts answering (so a check
can start friends' apps while the market is still "down"), and runs until it is killed."""
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'maple-cloud', 'tests'))
import test_cloud as T                                       # noqa: E402 (sets the paths up and imports the function as C)

PAGE = os.path.join(ROOT, 'maple-cloud', 'public', 'index.html')


class Handler(T.C.handler):
    """The function, and the page at / (a plain file on Vercel)."""
    def do_GET(self):
        if urlparse(self.path).path in ('/', '/index.html'):
            with open(PAGE, 'rb') as f:
                return self._send(200, f.read(), 'text/html; charset=utf-8')
        if urlparse(self.path).path == '/favicon.ico':
            return self._send(404, 'Not found', 'text/plain')
        return super().do_GET()


def main(port, names):
    pg = T.PG()
    try:
        pg.sql('create role anon; create role authenticated; create role service_role bypassrls;')
        with open(os.path.join(ROOT, 'maple-cloud', 'schema.sql'), encoding='utf-8') as f:
            pg.sql(f.read())
        pg.sql('grant all on all tables in schema public to service_role; grant all on all sequences in schema public to service_role;')
        keys = {n: pg.sql("select maple_add_key(:'n');", n=n) for n in names}
        sb = T.fake_supabase(pg)
        os.environ['SUPABASE_URL'] = f'http://127.0.0.1:{sb.server_address[1]}'
        os.environ['SUPABASE_SECRET_KEY'] = T.SECRET
        print(json.dumps(keys), flush=True)
        sys.stdin.readline()                                 # "go": the market comes online
        s = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        print('serving', flush=True)
        threading.Event().wait()                             # until killed
    finally:
        pg.stop()


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2:])
