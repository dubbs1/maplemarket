"""Checks the app's server and controller: the page is served, the state answers, settings are kept, the run log can be
named, pictures are served safely, and requests that don't come from this PC's own window are refused."""
import json, os, sys, tempfile, urllib.error, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
work = tempfile.mkdtemp(prefix='sapline_server_')
os.environ.setdefault('SAPLINE_UPDATE_API', 'off')    # these checks never ask GitHub (test_update.py does that)
os.chdir(work)
import sapline.config as C                           # noqa: E402
C.APP_DIR = work
from sapline import controller as CT, server as SV   # noqa: E402
CT.APP_DIR, CT.SETTINGS = work, os.path.join(work, 'settings.json')
TEST_PORTS = range(8790, 8796)                          # never the real app's port, in case it is open


def get(url, host=None):
    req = urllib.request.Request(url, headers={'Host': host} if host else {})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode('utf-8', 'replace')


def post(url, body, header=True):
    hdr = {'Content-Type': 'application/json'}
    if header:
        hdr['X-Sapline'] = '1'
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=hdr)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def main():
    ctl = CT.Controller()
    srv = SV.AppServer(controller=ctl, ports=TEST_PORTS)
    url = srv.start()
    fails = []

    def ok(name, cond):
        print(('ok     ' if cond else 'FAILED ') + name)
        if not cond:
            fails.append(name)

    ok('the server starts at ' + str(url), bool(url))
    code, page = get(url)
    ok('the page is served, titled Sapline', code == 200 and '<title>Sapline</title>' in page and 'data-nav="exp"' in page)
    st = json.loads(get(url + 'api/state')[1])
    ok('the state carries the version, settings, EXP and the run log', st['version'] and 'exp' in st and 'exp_log' in st and
       st['settings']['idle_min'] == 1 and st['exp_on'] is False)
    try:
        get(url, host='evil.example:1')
        ok('a request for another host is refused', False)
    except urllib.error.HTTPError as e:
        ok('a request for another host is refused (403)', e.code == 403)
    try:
        post(url + 'api/set', {'idle_min': 5}, header=False)
        ok('a button press without the window header is refused', False)
    except urllib.error.HTTPError as e:
        ok('a button press without the window header is refused (403)', e.code == 403)
    ok('settings: pause after 5 minutes', post(url + 'api/set', {'idle_min': 5})['ok'] and ctl.settings['idle_min'] == 5 and ctl.exp.idle == 300
       and json.load(open(CT.SETTINGS))['idle_min'] == 5)
    ok('settings: out-of-range minutes are clamped', post(url + 'api/set', {'idle_min': 99})['ok'] and ctl.settings['idle_min'] == 30)
    ok('settings: the run log switch', post(url + 'api/set', {'exp_log': False})['ok'] and ctl.settings['exp_log'] is False)
    ok('settings: start on open is off until switched on, and old keys are dropped', ctl.settings['autostart'] is False
       and 'monitor' not in ctl.settings and 'exp' not in ctl.settings and post(url + 'api/set', {'autostart': True})['ok'] and ctl.settings['autostart'] is True)
    for path in ('api/mob-name', 'api/mobpic/22.png'):                      # the mob pages are gone (2026-11-15)
        try:
            post(url + path, {}) if path.endswith('name') else get(url + path)
            ok(f'{path}: 404', False)
        except urllib.error.HTTPError as e:
            ok(f'{path}: 404 (the mob names and pictures are gone)', e.code == 404)
    try:
        post(url + 'api/nothing', {})
        ok('an unknown button is 404', False)
    except urllib.error.HTTPError as e:
        ok('an unknown button is 404', e.code == 404)
    ok('reset', post(url + 'api/exp-reset', {})['ok'])
    # the run log exported as a spreadsheet
    ctl.exp_log.add({'date': 1_700_000_000, 'minutes': 30, 'gained': 6000, 'per_hour': 12000, 'level': 39, 'map': 'Kerning City', 'party': None,
                     'mesos': None, 'mesos_per_hour': None, 'kills_total': 9, 'taken': 100,
                     'kills': [{'exp': 22, 'n': 6}, {'exp': 45, 'n': 3}]})
    ctl.exp_log.add({'date': 1_700_003_600, 'minutes': 45, 'gained': 9000, 'per_hour': 12000, 'level': 40, 'map': 'Subway', 'party': 2,
                     'mesos': 5000, 'mesos_per_hour': 6667, 'kills_total': 13, 'taken': 50, 'name': 'Evening hunt',
                     'kills': [{'exp': 22, 'n': 12}, {'exp': 60, 'n': 1}]})
    r = post(url + 'api/export-runs', {})
    raw = open(os.path.join(work, 'scans', 'runs.csv'), 'rb').read()
    lines = raw.decode('utf-8-sig').splitlines()
    ok('the run log exports to scans/runs.csv with a BOM, a header and one row per run', r == {'ok': True, 'file': 'runs.csv', 'rows': 2}
       and raw.startswith(b'\xef\xbb\xbf') and lines[0] == 'date,name,level,party,minutes,gained,exp_per_hour,mesos,mesos_per_hour,kills,damage_taken'
       and len(lines) == 3 and lines[1].endswith(',Evening hunt,40,2,45,9000,12000,5000,6667,13,50')
       and lines[2].endswith(',Kerning City,39,,30,6000,12000,,,9,100'))
    st = json.loads(get(url + 'api/state')[1])
    ok('how long the EXP line has been missing is None while not recording', st['exp_lost_s'] is None)
    # Stop then Start at once: the old recorder's screen capture is closed before the new one opens (one camera per screen)
    import types, time
    class Shot:
        def __init__(s, w, h): s.size, s.bgra = (w, h), bytes((9, 9, 9, 255)) * (w * h)
    opened, closed = [], []
    class Sct:
        monitors = [{}, {}]
        def __init__(s): opened.append(s)
        def grab(s, mon): time.sleep(0.05); return Shot(64, 32)
        def close(s): closed.append(s)
    sys.modules['mss'] = types.SimpleNamespace(MSS=lambda: Sct())
    ctl.settings['capture'] = 'standard'
    ctl.exp_start(); first = ctl._last_thread; time.sleep(0.3)
    ctl.exp_stop(); ctl.exp_start(); second = ctl._last_thread
    ok('Stop then Start: the first recorder had closed its capture before the second opened', first is not second and not first.is_alive()
       and len(closed) >= 1 and closed[0] is opened[0] and len(opened) == 2)
    r = ctl.screenshot()
    ok('Save a screenshot right after Start waits for the first picture instead of opening a second camera', r['ok'] and len(opened) == 2
       and os.path.exists(os.path.join(work, 'scans', r['file'])))
    ctl.exp_stop(); time.sleep(0.3)
    r = ctl.screenshot()
    ok('not recording: a screenshot opens its own capture and closes it', r['ok'] and len(opened) == 3 and closed[-1] is opened[-1])
    srv.stop()
    ctl.shutdown()
    print('SERVER CHECK PASSED' if not fails else 'SERVER CHECK FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
