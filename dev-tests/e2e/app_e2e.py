"""The app in a real browser: the page (Sapline) served by the app, with a pretend screen that shows a status bar.
   python3 dev-tests/e2e/app_e2e.py [Sapline folder] [screenshot prefix]   (needs: pip install playwright)"""
import sys, os, types, time, json, tempfile, asyncio, urllib.request, urllib.error
os.environ.setdefault('SAPLINE_UPDATE_API', 'off')   # never ask the real GitHub from a test
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the repository
R = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_ROOT, 'Sapline')
OUT = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix='sapline_shots_')   # screenshots go here
sys.path.insert(0, R)
work = tempfile.mkdtemp(prefix='sapline_app_'); os.chdir(work)
import sapline.config as C; C.APP_DIR = work
from PIL import Image
BAR = Image.open(os.path.join(R, 'tests', 'fixtures', 'live_shop.png')).convert('RGB')   # a screen with the status bar: 93,499 (43.17%), level 37
class Shot:
    def __init__(s, img): s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')
class Screen:
    monitors = [{}, {}]
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def grab(s, mon):
        time.sleep(0.05)
        return Shot(BAR)
sys.modules['mss'] = types.SimpleNamespace(MSS=lambda: Screen())
import sapline.controller as CT, sapline.server as SV
CT.APP_DIR = work; CT.SETTINGS = os.path.join(work, 'settings.json')
ctl = CT.Controller(); srv = SV.AppServer(controller=ctl); url = srv.start(); print('url', url)
fails = []
def ok(n, c):
    print(('PASS ' if c else 'FAIL ') + n)
    if not c: fails.append(n)
# safety: buttons can't be pressed by other pages
for hdr, want in (({}, 403), ({'X-Sapline': '1', 'Host': 'evil.example'}, 403)):
    try:
        urllib.request.urlopen(urllib.request.Request(url + 'api/set', data=b'{}', headers=hdr)); ok(f'S0 blocked {hdr}', False)
    except urllib.error.HTTPError as e: ok(f'S0 press without the app header/host is refused ({e.code})', e.code == want)
ok('S0b nothing recording yet', ctl.exp_runner is None)
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['PW_CHROMIUM']} if os.environ.get('PW_CHROMIUM') else {}))
        for scheme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 1240, 'height': 860}, color_scheme=scheme)
            pg = await ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(url); await pg.wait_for_timeout(1800)
            if scheme == 'dark':
                ok('A1 opens on the EXP tab', await pg.get_attribute('[data-nav=exp]', 'aria-current') == 'page')
                ok('A1b night first', await pg.evaluate("document.documentElement.dataset.theme") == 'dark')
                ok('A2 says not recording', 'Not recording' in await pg.inner_text('#chip') and 'Start' in await pg.inner_text('.xctl'))
                ok('A2b no update card when there is nothing to update', await pg.locator('#upd').count() == 0)
                ok('A2e before any reading, Home explains what to check and nothing records by itself', 'Three things to check' in await pg.inner_text('#app')
                   and 'Press Start recording' in await pg.inner_text('#chipsub') and ctl.settings.get('autostart') is False)
                ctl.update_info = {'state': 'available', 'version': '2099-01-01', 'can_install': False, 'page': 'https://example.com/r'}
                await pg.wait_for_timeout(1600)
                ok('A2c a new version shows at the top of EXP', await pg.locator('#upd').count() == 1 and
                   'New version 2099-01-01' in await pg.inner_text('#upd') and 'Download page' in await pg.inner_text('#upd'))
                ctl.update_info = {'state': 'none'}; await pg.wait_for_timeout(1600)
                ok('A2d and goes away again', await pg.locator('#upd').count() == 0)
                await pg.screenshot(path=OUT + '_idle.png')
                await pg.click('[data-x=go]'); await pg.wait_for_timeout(1500)
                ok('A3 Start starts the recorder', ctl.exp_runner is not None and 'Stop' in await pg.inner_text('.xctl'))
                # the tracker starts once two readings (a second apart) agree
                for _ in range(25):
                    xt = await pg.inner_text('#app')
                    if '43.17%' in xt:
                        break
                    await pg.wait_for_timeout(1000)
                ok(f'A4 the EXP tab read the status bar (level 37, 43.17%) {xt[:50]!r}', '37' in xt and '43.17%' in xt and '93,499' in xt)
                ok('A4b the header pill shows Recording and the level', 'Recording' in await pg.inner_text('#chip') and 'Lv 37' in await pg.inner_text('#chip'))
                ok('A4c the Next up card is there, waiting for kills', 'Next up' in xt and 'kills to level' in xt.lower() and 'kills per hour' in xt.lower())
                ok('A4f the status card explains itself', 'EXP an hour' in await pg.inner_text('#chipsub') or 'once a second' in await pg.inner_text('#chipsub'))
                ok('A4d the first minutes are marked as a warm-up', await pg.locator('#app .warm').count() == 1)
                ok('A4e the level card and the session tiles', await pg.locator('.xlv').count() == 1 and 'damage taken' in xt.lower() and 'This session' in xt)
                await pg.click('[data-xr=week]'); await pg.wait_for_timeout(300)
                ok('A5 the last 7 days chart', 'EXP per day' in await pg.inner_text('#app') and await pg.locator('.xchart i').count() == 7)
                await pg.click('[data-xk=line]'); await pg.wait_for_timeout(300)
                ok('A5b as a line too, with a log scale on offer', await pg.locator('svg.xline polyline').count() == 1 and
                   await pg.locator('svg.xline circle').count() == 7 and await pg.locator('[data-xs=log]').count() == 1)
                await pg.click('[data-xs=log]'); await pg.wait_for_timeout(300)
                ok('A5c log scale remembered', await pg.evaluate("() => JSON.parse(localStorage.getItem('sap1:charts')).xs") is True)
                await pg.click('[data-xk=bars]'); await pg.click('[data-xs=lin]'); await pg.click('[data-xr=session]'); await pg.wait_for_timeout(300)
                await pg.screenshot(path=OUT + '_exp.png')
                await pg.click('[data-x=reset]'); await pg.wait_for_timeout(1500)
                ok('A6 Reset clears it (until the next readings)', ctl.exp.gained == 0 and ctl.exp.levels == 0 and 'Counting again' in await pg.inner_text('#live'))
                # Runs
                for i, m in enumerate(('The Land of Wild Boar II', 'Ant Tunnel I')):
                    ctl.exp_log.add({'date': time.time() - 3600 * (i + 1), 'minutes': 45, 'gained': 40000, 'per_hour': 53333, 'level': 37, 'map': m, 'party': 4 - i * 3,
                                     'kills': [{'exp': 20, 'n': 30, 'name': 'Snail'}], 'kills_total': 30, 'taken': 120})
                await pg.click('[data-nav=runs]'); await pg.wait_for_timeout(1500)
                rt = await pg.inner_text('.xlog')
                ok('A7 the Runs tab lists past runs, with the party, kills and damage', await pg.locator('.xlog tbody tr:not(.now)').count() == 2 and
                   'Ant Tunnel I' in rt and '4 in party' in rt and 'dmg taken' in rt.lower())
                await pg.click('.xlog [data-xl=rename] >> nth=0'); await pg.fill('#xrn', 'Boars with Sam'); await pg.wait_for_timeout(1500)
                ok('A7b typing a name is not wiped by the page refreshing', await pg.input_value('#xrn') == 'Boars with Sam')
                await pg.press('#xrn', 'Enter'); await pg.wait_for_timeout(1500)
                ok('A7c Enter in the box saves the new name', ctl.exp_log.list()[0].get('name') == 'Boars with Sam' and 'Boars with Sam' in await pg.inner_text('.xlog'))
                await pg.click('.xlog [data-xl=delete] >> nth=1'); await pg.wait_for_timeout(1500)
                ok('A7d Delete removes a line', len(ctl.exp_log.list()) == 1 and await pg.locator('.xlog tbody tr:not(.now)').count() == 1)
                await pg.click('[data-xl=on]'); await pg.wait_for_timeout(1000)
                ok('A7e "Log my runs" can be turned off', ctl.settings['exp_log'] is False)
                rt = (await pg.inner_text('#app')).lower()
                ok('A7f the week summary above the log', 'best map this week' in rt and 'longest run' in rt and 'ant tunnel i' in rt)
                await pg.click('[data-xl=on]'); await pg.wait_for_timeout(800)
                await pg.screenshot(path=OUT + '_runs.png')
                # Mobs
                ctl.exp.amounts = {22: 5, 45: 1}       # (as if kills had been seen)
                await pg.click('[data-nav=mobs]'); await pg.wait_for_timeout(1500)
                mt = await pg.inner_text('#app')
                ok('A8 the Mobs tab lists the kills by EXP amount, with a name box', await pg.get_attribute('input.mn', 'data-mn') == '22'
                   and 'Other gains' in mt and await pg.locator('input.mn').count() == 1 and '22 EXP' in mt)
                await pg.click('[data-mns]'); await pg.wait_for_timeout(300)
                ok('A8a Save with an empty name just asks for one', 'name first' in await pg.inner_text('#live') and ctl.mobs.name(22) is None)
                await pg.fill('input.mn', 'Evil Eye'); await pg.press('input.mn', 'Enter'); await pg.wait_for_timeout(1500)
                ok('A8b naming a mob goes into mobs.txt and the table', ctl.mobs.name(22) == 'Evil Eye' and 'Evil Eye' in await pg.inner_text('#app')
                   and 'Evil Eye | 22' in open(os.path.join(work, 'mobs.txt'), encoding='utf-8').read())
                r = await pg.evaluate("() => fetch('/api/mobpic/22.png').then(r => r.status)")
                ok('A8c no picture of it yet: 404, not an error', r == 404)
                await pg.screenshot(path=OUT + '_mobs.png')
                # Options
                await pg.click('[data-nav=more]'); await pg.wait_for_timeout(500)
                ok('A9 Settings: every setting is a row with a sentence, no screen choice, with the stance text', await pg.locator('#app .opt').count() >= 7 and
                   await pg.locator('#om').count() == 0 and 'only looks at your screen' in await pg.inner_text('#app') and 'You have' in await pg.inner_text('#updline'))
                await pg.select_option('#oi', '5'); await pg.check('#ox'); await pg.wait_for_timeout(1500)
                st = json.load(open(os.path.join(work, 'settings.json')))
                ok('A9b settings saved (pause after 5, start on open), and nothing else is stored', st['idle_min'] == 5 and st['autostart'] is True
                   and 'monitor' not in st and 'exp' not in st and ctl.exp.idle == 300)
                ok('A9c the start-on-open switch does not touch the recording going on', ctl.exp_runner is not None)
                await pg.click('[data-x=go]'); await pg.wait_for_timeout(1500)
                ok('A9d Stop recording in the menu stops it; the switch stays as set', ctl.exp_runner is None and await pg.is_checked('#ox'))
                await pg.click('[data-x=go]'); await pg.uncheck('#ox'); await pg.wait_for_timeout(1500)
                ok('A9e and Start starts it again', ctl.exp_runner is not None and ctl.settings['autostart'] is False)
                await pg.click('#theme'); await pg.wait_for_timeout(200)     # this browser asks for dark, so the first click gives day
                lt = await pg.evaluate("document.documentElement.dataset.theme"); await pg.screenshot(path=OUT + '_day.png')
                await pg.click('#theme'); await pg.wait_for_timeout(200)
                ok(f'A10 the Look button in Settings switches day and night (first {lt})', lt == 'light' and
                   await pg.evaluate("document.documentElement.dataset.theme") == 'dark')
                await pg.screenshot(path=OUT + '_options.png')
                await pg.click('[data-nav=exp]'); await pg.wait_for_timeout(800)
                await pg.click('[data-x=go]'); await pg.wait_for_timeout(1500)
                ok('A11 Stop stops', ctl.exp_runner is None and 'Start' in await pg.inner_text('.xctl'))
                await pg.reload(); await pg.wait_for_timeout(2000)
                ok('A12 reload: still the EXP tab, still not recording', 'Not recording' in await pg.inner_text('#chip'))
            else:
                await pg.wait_for_timeout(500); await pg.screenshot(path=OUT + '_light.png')
                await pg.set_viewport_size({'width': 420, 'height': 900}); await pg.wait_for_timeout(500)
                sw = await pg.evaluate('document.documentElement.scrollWidth')
                ok(f'A13 phone width: no sideways scroll ({sw})', sw <= 420)
                await pg.screenshot(path=OUT + '_narrow.png', full_page=False)
            ok(f'A14 no page errors ({scheme}) {errs[:2]}', not errs)
            await ctx.close()
        await b.close()
asyncio.run(main())
srv.stop(); ctl.shutdown()
print('ALL APP CHECKS PASSED' if not fails else f'{len(fails)} FAILED')
sys.exit(1 if fails else 0)
