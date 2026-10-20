import os
import sys, os, time, json, subprocess, tempfile, asyncio, shutil, urllib.request
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the repository
R = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_ROOT, 'MapleReader')
SRV = sys.argv[2] if len(sys.argv) > 2 else os.path.join(_ROOT, 'maple-server')
OUT = sys.argv[3] if len(sys.argv) > 3 else tempfile.mkdtemp(prefix='mr_shots_'); HERE = os.path.dirname(os.path.abspath(__file__))
data = tempfile.mkdtemp(prefix='maple_share_')
env = dict(os.environ, MAPLE_DATA=data, MAPLE_PORT='8799', MAPLE_QUIET='1')
mk = lambda name: subprocess.run([sys.executable, os.path.join(SRV, 'manage.py'), 'add', name], capture_output=True, text=True, env=env).stdout.split(f'Key for {name}:')[1].split()[0]
kA, kB = mk('Cass'), mk('Gunther')
server = 'http://127.0.0.1:8799'
fails = []
def ok(n, c):
    print(('PASS ' if c else 'FAIL ') + n)
    if not c: fails.append(n)
wA, wB, wC = (tempfile.mkdtemp(prefix=f'friend{x}_') for x in 'ABC')
# friend A starts BEFORE the server is up (offline at first)
pA = subprocess.Popen([sys.executable, os.path.join(HERE, 'friend.py'), R, wA, '8766', kA, server, 'session', '150'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pC = subprocess.Popen([sys.executable, os.path.join(HERE, 'friend.py'), R, wC, '8768', 'mm-wrong-key', server, 'session', '40'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(12)
stA = json.load(open(os.path.join(wA, 'status.json')))
ok(f"A: server down -> scans kept, says offline ({stA['share']['state']})", stA['share']['state'] in ('offline', 'retrying'))
psrv = subprocess.Popen([sys.executable, os.path.join(SRV, 'server.py')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)
pB = subprocess.Popen([sys.executable, os.path.join(HERE, 'friend.py'), R, wB, '8767', kB, server, 'session', '130'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pB2 = None
time.sleep(70)
stC = json.load(open(os.path.join(wC, 'status.json')))
ok(f"C: wrong key -> told clearly ({stC['share']['state']})", stC['share']['state'] == 'bad-key')
# B then also scans the long screw shop on another channel (only B has it)
from playwright.async_api import async_playwright
rows = lambda: json.loads(urllib.request.urlopen(server + '/api/rows?from=0').read())
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['PW_CHROMIUM']} if os.environ.get('PW_CHROMIUM') else {}))
        pg = await (await b.new_context(viewport={'width': 1240, 'height': 900})).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(server + '/'); await pg.wait_for_timeout(3000)
        f = rows()
        n_lines = f['text'].count('\n')
        print('server has', n_lines, 'rows; scanning now', f['status']['scanning'])
        ok('both friends\' scans reached the server (A after coming online)', n_lines >= 50)
        sale = await pg.evaluate("() => window.App.analyze().rows.filter(o=>o.st==='sale').length")
        sold = await pg.evaluate("() => window.App.analyze().rows.filter(o=>o.st==='sold').length")
        ok(f'shared page: the same shops scanned by two friends count once ({sale} for sale, {sold} sold)', sale == 20 and sold == 9)
        ok('shared page has no Scanner tab', await pg.locator('[data-nav=scan]').is_hidden())
        ok('chip shows people scanning: ' + await pg.inner_text('#chip'), 'scanning now' in await pg.inner_text('#chip'))
        await pg.click('[data-nav=market]'); await pg.wait_for_timeout(800)
        await pg.wait_for_timeout(1500)   # the picture list arrives a moment after the rows
        shown = await pg.locator('#mb .fr').count(); pics = await pg.locator('#mb img.ic').count()
        ok(f'shared page shows the pictures friends sent ({pics} of {shown} rows)', shown >= 15 and pics == shown)
        await pg.screenshot(path=OUT + '_shared.png')
        # B scans a shop only B saw -> appears for everyone, and in A's own app Market tab
        nonlocal_pB2[0] = subprocess.Popen([sys.executable, os.path.join(HERE, 'friend.py'), R, tempfile.mkdtemp(prefix='friendB2_'), '8769', kB, server, 'screw', '60'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            await pg.wait_for_timeout(1000)
            if await pg.evaluate("() => window.App.analyze().rows.filter(o=>o.room===0 && o.ch===3).length") >= 20: break
        got = await pg.evaluate("() => window.App.analyze().rows.filter(o=>o.ch===3).length")
        ok(f"a friend's new shop appears on the shared page by itself ({got} rows)", got == 20)
        pa = await (await b.new_context(viewport={'width': 1240, 'height': 900})).new_page()
        await pa.goto('http://127.0.0.1:8766/'); await pa.wait_for_timeout(6000)
        await pa.click('[data-nav=market]'); await pa.wait_for_timeout(1500)
        got = await pa.evaluate("() => window.App.analyze().rows.filter(o=>o.ch===3).length")
        ok(f"…and in A's own app Market tab ({got})", got == 20)
        await pa.click('[data-nav=scan]'); await pa.wait_for_timeout(1500)
        await pa.click('#sets summary'); shst = await pa.inner_text('#shst')
        ok('A sees "Sharing as Cass · N sent": ' + shst, 'Sharing as Cass' in shst)
        await pa.screenshot(path=OUT + '_appshare.png', full_page=True)
        ok(f'no page errors {errs[:2]}', not errs)
        await b.close()
nonlocal_pB2 = [None]
asyncio.run(main())
for pr in (pA, pB, pC, psrv, nonlocal_pB2[0]):
    if pr: pr.kill()
print('ALL SHARE CHECKS PASSED' if not fails else f'{len(fails)} FAILED')
