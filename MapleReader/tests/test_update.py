"""Checks updates (against a pretend GitHub on this PC) and the installed app's first run (bringing old scans over).
Run with run_tests.bat (or: py -3.13 tests/test_update.py)."""
import hashlib, json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
work = tempfile.mkdtemp(prefix='maplereader_update_')
import shopreader.config as C                           # noqa: E402
C.APP_DIR = work
from shopreader import update, migrate                  # noqa: E402

SETUP = b'pretend setup program ' * 1000
FILES = {}                                              # path -> (status, body)


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        code, body = FILES.get(self.path, (404, b'{"message": "Not Found"}'))
        self.send_response(code)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def release(tag, sha=None, with_sha=True):
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    name = f'MapleReader-Setup-{tag.lstrip("v")}.exe'
    assets = [{'name': name, 'browser_download_url': base + '/dl/' + name}]
    if with_sha:
        assets.append({'name': name + '.sha256', 'browser_download_url': base + '/dl/' + name + '.sha256'})
        FILES['/dl/' + name + '.sha256'] = (200, ((sha or hashlib.sha256(SETUP).hexdigest()) + '  ' + name + '\n').encode())
    FILES['/dl/' + name] = (200, SETUP)
    FILES['/latest'] = (200, json.dumps({'tag_name': tag, 'assets': assets, 'html_url': base + '/page', 'body': 'Faster.'}).encode())


def main():
    global srv
    srv = ThreadingHTTPServer(('127.0.0.1', 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    api = 'http://127.0.0.1:%d/latest' % srv.server_address[1]
    fails = []

    def ok(name, cond):
        print(('ok     ' if cond else 'FAILED ') + name)
        if not cond:
            fails.append(name)

    # --- finding an update ---
    release('v2099-01-01')
    info = update.check(api, current='2026-10-20f')
    ok('a newer release is found', info['state'] == 'available' and info['version'] == '2099-01-01')
    ok('the same version is not offered again', update.check(api, current='2099-01-01')['state'] == 'none')
    ok('an older release is not offered', update.check(api, current='2100-01-01')['state'] == 'none')
    rel = json.loads(FILES['/latest'][1])
    for a in rel['assets']:
        a['browser_download_url'] = 'https://elsewhere.example' + a['browser_download_url'].split('/dl')[1]
    FILES['/latest'] = (200, json.dumps(rel).encode())
    ok('files that are not on the release page are never downloaded', update.check(api, current='2026-10-20f')['state'] == 'none')
    FILES.pop('/latest')
    ok('no public release (private repository or none yet): says so quietly', update.check(api)['state'] == 'unavailable')
    ok('offline: says so quietly', update.check('http://127.0.0.1:9/latest')['state'] == 'offline')
    release('v2099-01-02', with_sha=False)
    ok('a release without a fingerprint is never offered', update.check(api, current='2026-10-20f')['state'] == 'none')
    os.environ['MAPLEREADER_UPDATE_API'] = 'off'
    ok('checking can be switched off', update.check()['state'] == 'off')
    del os.environ['MAPLEREADER_UPDATE_API']

    # --- downloading it ---
    release('v2099-01-03')
    info = update.check(api, current='2026-10-20f')
    path = update.download(info, os.path.join(work, 'updates'))
    ok('the download is kept when its fingerprint matches', open(path, 'rb').read() == SETUP)
    release('v2099-01-04', sha='0' * 64)
    info = update.check(api, current='2026-10-20f')
    try:
        update.download(info, os.path.join(work, 'updates2'))
        ok('a download that does not match its fingerprint is refused', False)
    except ValueError:
        ok('a download that does not match its fingerprint is refused, and deleted',
           not os.listdir(os.path.join(work, 'updates2')))
    ps = update.install_script(r"C:\Users\O'Neil x\MapleReader\updates\MapleReader-Setup-2099-01-03.exe", 4321,
                               r"C:\Users\O'Neil x\MapleReader\MapleReader.exe")
    ok('the install script waits for this app (its process, then any MapleReader.exe from the app folder), runs the setup '
       'quietly with a log, and starts MapleReader again if the setup did not',
       'Wait-Process -Id 4321 ' in ps and "$exe = 'C:\\Users\\O''Neil x\\MapleReader\\MapleReader.exe'" in ps and
       "$psi.FileName = 'C:\\Users\\O''Neil x\\MapleReader\\updates\\MapleReader-Setup-2099-01-03.exe'" in ps and
       "$psi.Arguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=\"C:\\Users\\O''Neil x\\MapleReader\\updates\\setup.log\"'" in ps and
       'could not be started' in ps and
       "$log = 'C:\\Users\\O''Neil x\\MapleReader\\updates\\install.log'" in ps and
       'if (-not (Running)) {' in ps and 'Start-Process -FilePath $exe' in ps and '"' not in ps.replace('/LOG=\"', '').replace('.log\"', ''))
    cmd = update.install_command(r'C:\x\updates\install.ps1')
    ok('the script runs as a file, hidden, whatever the PC\'s script policy', cmd[0].lower().endswith('powershell.exe') and
       cmd[-2:] == ['-File', r'C:\x\updates\install.ps1'] and '-ExecutionPolicy' in cmd and 'Hidden' in cmd)

    # --- the app's Update now ---
    from shopreader import controller as CT
    CT.APP_DIR, CT.SETTINGS = work, os.path.join(work, 'settings.json')
    os.environ['MAPLEREADER_UPDATE_API'] = api
    release('v2099-01-05')
    ctl = CT.Controller()
    ctl.check_update(wait=True)
    ok('the app sees the update', ctl.snapshot()['update']['state'] == 'available')
    ok('the zip version is sent to the download page instead', ctl.install_update()['ok'] is False)
    started = []
    CT.updater.start_install = lambda p, pid=None, app_exe=None: started.append(p)
    ctl.frozen = True
    ctl.update_info['can_install'] = True
    ctl.install_update()
    for _ in range(50):
        if ctl.quit_requested:
            break
        threading.Event().wait(0.1)
    ok('installed app: downloads, checks, starts the setup and closes', ctl.quit_requested and started and
       ctl.update_info['state'] == 'installing' and open(started[0], 'rb').read() == SETUP)
    pending = os.path.join(work, 'updates', 'pending.json')
    ok('...and notes which version it is going for', json.load(open(pending))['to'] == '2099-01-05')
    # the next start of the installed app says how it went (sys.frozen pretended, as in the exe)
    sys.frozen = True
    try:
        with open(os.path.join(work, 'updates', 'install.log'), 'w', encoding='utf-8-sig') as f:
            f.write('2026-10-24T12:00:00 running the setup\n2026-10-24T12:00:09 the setup finished with code 5\n2026-10-24T12:00:14 done\n')
        notes = [e for e in CT.Controller().snapshot()['events'] if e.get('kind') == 'note']
        ok('a failed update is reported at the next start, with the log lines', any('did not install' in n['text'] and
           'finished with code 5' in n['text'] and 'install.log' in n['text'] for n in notes))
        ok('...the setup file and script are dropped, the logs and the scans stay',
           not os.path.exists(pending) and not os.path.exists(started[0]) and
           os.path.exists(os.path.join(work, 'updates', 'install.log')))
        with open(pending, 'w') as f:
            json.dump({'from': '2000-01-01', 'to': CT.__version__, 't': 0}, f)
        notes = [e for e in CT.Controller().snapshot()['events'] if e.get('kind') == 'note']
        ok('a finished update says so once', any(n['text'] == f'Updated to MapleReader {CT.__version__}.' for n in notes)
           and not os.path.exists(pending))
        ok('no marker: nothing said', not any('pdate' in e.get('text', '') for e in CT.Controller().snapshot()['events']))
    finally:
        del sys.frozen
    del os.environ['MAPLEREADER_UPDATE_API']

    # --- first run of the installed app: old scans come along ---
    home = tempfile.mkdtemp(prefix='maplereader_home_')
    old = os.path.join(home, 'OneDrive', 'Desktop', 'MapleReader')
    os.makedirs(os.path.join(old, 'scans', 'icons'))
    for rel, text in (('scans/all_scans.txt', 'Ice Wand | 12500 | WCC | 2 | 10\n'), ('scans/icons/ice-wand.png', 'png'),
                      ('scans/share_state.json', '{}'), ('settings.json', '{"volume": 0.2}'), ('items.txt', 'Ice Wand\n')):
        with open(os.path.join(old, rel), 'w') as f:
            f.write(text)
    before = sorted(os.walk(old))
    app = tempfile.mkdtemp(prefix='maplereader_installed_')
    env = {'USERPROFILE': home, 'OneDrive': os.path.join(home, 'OneDrive')}
    msg = migrate.first_run(app, env)
    ok(f'first run brings the old scans over ({msg})', msg and 'Brought over' in msg and
       open(os.path.join(app, 'scans', 'all_scans.txt')).read().startswith('Ice Wand') and
       os.path.isfile(os.path.join(app, 'scans', 'icons', 'ice-wand.png')) and os.path.isfile(os.path.join(app, 'settings.json')))
    ok("where sharing got to isn't copied", not os.path.exists(os.path.join(app, 'scans', 'share_state.json')))
    ok('the old folder is left as it was', sorted(os.walk(old)) == before)
    ok('it only happens once', migrate.first_run(app, env) is None)
    ok('no old folder: nothing happens', migrate.first_run(tempfile.mkdtemp(), {'USERPROFILE': tempfile.mkdtemp()}) is None)
    srv.shutdown()
    print('UPDATE CHECK PASSED' if not fails else 'UPDATE CHECK FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
