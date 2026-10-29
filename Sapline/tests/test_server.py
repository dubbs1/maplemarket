"""Checks the app's server and controller: the page is served, the state answers, settings are kept, a mob can be
named, pictures are served safely, and requests that don't come from this PC's own window are refused."""
import json, os, socket, sys, tempfile, urllib.error, urllib.request
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
    from PIL import Image
    ctl = CT.Controller()
    ctl.mobpics.keep(22, Image.new('RGB', (8, 8), (200, 40, 40)))
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
    ok('naming a mob writes mobs.txt', post(url + 'api/mob-name', {'exp': 22, 'name': 'Evil Eye'})['ok'] and ctl.mobs.name(22) == 'Evil Eye')
    ok('a bad name is refused', not post(url + 'api/mob-name', {'exp': 22, 'name': 'a|b'})['ok'])
    ok('the mob picture is served', get(url + 'api/mobpic/22.png')[0] == 200)
    for path in ('api/mobpic/23.png', 'api/mobpic/../settings.json', 'api/mobpic/x.png'):
        try:
            get(url + path)
            ok(f'{path}: 404', False)
        except urllib.error.HTTPError as e:
            ok(f'{path}: 404', e.code == 404)
    s = socket.create_connection(('127.0.0.1', srv.httpd.server_address[1]), timeout=5)   # a digit that isn't ASCII
    s.sendall(b'GET /api/mobpic/\xb2.png HTTP/1.0\r\nHost: 127.0.0.1:%d\r\n\r\n' % srv.httpd.server_address[1])
    ok('a non-ASCII digit in a picture name is a 404, not an error', b' 404 ' in s.recv(200))
    s.close()
    ok('forgetting a picture', post(url + 'api/mob-name', {'exp': 22, 'action': 'forget'})['ok'] and 22 not in ctl.mobpics.have)
    try:
        post(url + 'api/nothing', {})
        ok('an unknown button is 404', False)
    except urllib.error.HTTPError as e:
        ok('an unknown button is 404', e.code == 404)
    ok('reset', post(url + 'api/exp-reset', {})['ok'])
    srv.stop()
    ctl.shutdown()
    print('SERVER CHECK PASSED' if not fails else 'SERVER CHECK FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
