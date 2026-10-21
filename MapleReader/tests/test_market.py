"""Checks the live market server: serves the page, hands out only new complete rows, starts over when
all_scans.txt is replaced, and refuses requests that don't come from this PC's own address."""
import json, os, sys, tempfile, urllib.error, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
work = tempfile.mkdtemp(prefix='maplereader_market_')
os.environ.setdefault('MAPLEREADER_UPDATE_API', 'off')    # these checks never ask GitHub (test_update.py does that)
import shopreader.config as C                           # noqa: E402
C.APP_DIR = work
from shopreader import market_server as M               # noqa: E402
M.APP_DIR = work
TEST_PORTS = range(8790, 8796)                          # never the real app's port, in case it is open


def get(url, host=None):
    req = urllib.request.Request(url, headers={'Host': host} if host else {})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode('utf-8')


def main():
    os.makedirs(os.path.join(work, 'scans'))
    path = M.all_scans_path()
    srv = M.MarketServer(lambda: {'watching': True, 'total': 2}, ports=TEST_PORTS)
    url = srv.start()
    fails = []

    def ok(name, cond):
        print(('ok     ' if cond else 'FAILED ') + name)
        if not cond:
            fails.append(name)

    ok('the market starts at ' + str(url), bool(url))
    code, page = get(url)
    ok('the page is served', code == 200 and 'Live from MapleReader' in page)
    rows = lambda start: json.loads(get(f'{url}api/rows?from={start}')[1])
    ok('no all_scans.txt yet: nothing to send', rows(0)['text'] == '')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('Bunny Ears | 62999 | Shop | 1 | 10 | @2026-10-19T15:31:08\nIce Wa')
    r = rows(0)
    ok('only complete lines are sent', r['text'].count('\n') == 1 and 'Ice' not in r['text'])
    ok('status comes along', r['status'] == {'watching': True, 'total': 2})
    with open(path, 'a', encoding='utf-8') as f:
        f.write('nd | 12500 | Shop | 1 | 10 | @2026-10-19T15:31:09\n')
    r2 = rows(r['next'])
    ok('the next request sends just the new line', r2['text'].startswith('Ice Wand'))
    os.remove(path)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('Dankke | 15000 | Shop | 1 | 10 | @2026-10-19T15:40:00\n')
    r3 = rows(r2['next'])
    ok('a replaced file is read from the top', r3['reset'] and r3['text'].startswith('Dankke'))
    try:
        get(url + 'api/rows', host='evil.example')
        ok('other addresses are refused', False)
    except urllib.error.HTTPError as e:
        ok('other addresses are refused', e.code == 403)
    second = M.MarketServer(ports=TEST_PORTS)
    ok('a second copy uses the running market', second.start() == url and second.shared)
    srv.stop()

    # the app's buttons: only the app window may press them
    from shopreader import controller as CT
    CT.APP_DIR, CT.SETTINGS = work, os.path.join(work, 'settings.json')
    ctl = CT.Controller()
    app = M.MarketServer(controller=ctl, ports=TEST_PORTS)
    url = app.start()
    state = json.loads(get(url + 'api/state')[1])
    ok('the app reports its state', state['version'] and state['watching'] is False)

    def press(path, body, headers):
        req = urllib.request.Request(url + path, data=json.dumps(body).encode(), headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, None
    ok('a button press from another page is refused', press('api/set', {'monitor': 2}, {})[0] == 403)
    code, r = press('api/set', {'monitor': 2, 'volume': 0.1}, {'X-MapleReader': '1', 'Content-Type': 'application/json'})
    saved = json.load(open(CT.SETTINGS))
    ok('a button press from the app window works and is remembered', code == 200 and r['ok'] and saved['monitor'] == 2)
    ok('a wrong channel is refused', press('api/set', {'channel': 99}, {'X-MapleReader': '1'})[1]['ok'] is False)
    ok('starting by itself is on unless switched off', ctl.settings['auto_start'] is True)
    press('api/set', {'channel': 5, 'room': 2}, {'X-MapleReader': '1'})
    ctl.start()
    kept = (ctl.scanner.state['ch'], ctl.scanner.state['room'], ctl.state['room']) if ctl.scanner else None
    ctl.stop()
    ok(f'a typed channel and room are kept when watching starts (Stop/Start, reopening): {kept}', kept == (5, 2, 2))
    press('api/set', {'auto_start': False}, {'X-MapleReader': '1'})
    ok('...and switching it off is remembered', json.load(open(CT.SETTINGS))['auto_start'] is False)
    app.stop()

    # no Tesseract when the app opened, installed later: the app notices without a restart
    import time
    real = CT.find_tesseract
    CT.find_tesseract = lambda: False
    late = CT.Controller()
    late.autostart()
    ok('without Tesseract it does not try to start', late.scanner is None and late.snapshot()['tesseract'] is False)
    CT.find_tesseract = real
    late._tess_check = 0
    late.snapshot()
    for _ in range(100):
        if late.tesseract:
            break
        time.sleep(0.1)
    ok('Tesseract installed while open: ready without a restart', late.snapshot()['tesseract'] is True)
    print('MARKET CHECK PASSED' if not fails else 'MARKET CHECK FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
