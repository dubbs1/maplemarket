import sys, os, types, time, json, tempfile, threading, asyncio, urllib.request, urllib.error
os.environ.setdefault('MAPLEREADER_UPDATE_API', 'off')   # never ask the real GitHub from a test
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the repository
R = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_ROOT, 'MapleReader')
OUT = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix='mr_shots_')   # screenshots go here
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, 'tests'))
work = tempfile.mkdtemp(prefix='mr_app_'); os.chdir(work)
import shopreader.config as C; C.APP_DIR = work
import test_session as TS
pics = TS.frames(); hold = {'go': False}
class Shot:
    def __init__(s, img): s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')
class Screen:
    monitors = [{}, {}]
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def grab(s, mon):
        if threading.current_thread().name == 'exp':   # the EXP recorder looks at the same screen, but takes no turns
            return Shot(pics[0])
        time.sleep(0.12)
        return Shot(pics.pop(0) if len(pics) > 1 else pics[0])
sys.modules['mss'] = types.SimpleNamespace(MSS=lambda: Screen())
import shopreader.controller as CT, shopreader.market_server as M
CT.APP_DIR = M.APP_DIR = work; CT.SETTINGS = os.path.join(work, 'settings.json')
ctl = CT.Controller(); srv = M.MarketServer(controller=ctl); url = srv.start(); print('url', url)
fails = []
def ok(n, c):
    print(('PASS ' if c else 'FAIL ') + n)
    if not c: fails.append(n)
# safety: buttons can't be pressed by other pages
for hdr, want in (({}, 403), ({'X-MapleReader': '1', 'Host': 'evil.example'}, 403)):
    try:
        urllib.request.urlopen(urllib.request.Request(url + 'api/start', data=b'{}', headers=hdr)); ok(f'S0 blocked {hdr}', False)
    except urllib.error.HTTPError as e: ok(f'S0 press without the app header/host is refused ({e.code})', e.code == want)
ok('S0b nothing started', not ctl.state['watching'])
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
                ok('A1 opens on the Scanner tab', await pg.get_attribute('[data-nav=scan]', 'aria-current') == 'page')
                ok('A2 says not scanning', 'Not scanning' in await pg.inner_text('#sst'))
                lb = await pg.evaluate("document.querySelector('.scan > div').getBoundingClientRect().bottom")
                ok(f'A1b the Scan tab fits the window without scrolling (left column ends at {lb:.0f} of 860)', lb <= 860)
                ok('A2b three steps to follow, none done yet', await pg.locator('#steps li').count() == 3 and await pg.locator('#steps li.done').count() == 0)
                ok('A2c channel and room boxes stay closed until Change', await pg.locator('#ich').is_hidden())
                ok('A2d group sharing is not shown while it is off', await pg.locator('#shst').count() == 0)
                ok('A2e no update card when there is nothing to update', await pg.locator('#upd').is_hidden())
                ctl.update_info = {'state': 'available', 'version': '2099-01-01', 'can_install': False, 'page': 'https://example.com/r'}
                await pg.wait_for_timeout(1600)
                ok('A2f a new version shows at the top of Scan', await pg.locator('#upd').is_visible() and
                   'A new version is ready' in await pg.inner_text('#upd') and 'Download page' in await pg.inner_text('#upd'))
                ctl.update_info = {'state': 'none'}; await pg.wait_for_timeout(1600)
                ok('A2g and goes away again', await pg.locator('#upd').is_hidden())
                await pg.screenshot(path=OUT + '_idle.png')
                await pg.click('[data-chg=ch]'); await pg.fill('#ich', '99'); await pg.click('#sch'); await pg.wait_for_timeout(300)
                ok('A3 bad channel refused', ctl.state['channel'] == 0)
                await pg.click('#expgo'); await pg.wait_for_timeout(1500)
                ok('A3b EXP has its own Start: recording EXP without watching shops', ctl.exp_runner is not None and
                   not ctl.state['watching'] and (await pg.inner_text('#expgo')) == 'Stop')
                await pg.click('#go'); await pg.wait_for_timeout(1500)
                ok('A4 Start starts the scanner', ctl.state['watching'] and 'Stop' in await pg.inner_text('#go'))
                t0 = time.time()
                while time.time() - t0 < 180 and ctl.state['total'] < 29:
                    await pg.wait_for_timeout(1000)
                await pg.wait_for_timeout(2500)
                n = await pg.locator('#feed .fr').count()
                ok(f'A5 all 29 listings appear in the feed ({n})', n == 29)
                imgs = await pg.locator('#feed img.ic').count()
                ok(f'A6 each has its picture ({imgs})', imgs == 29)
                ok('A7 channel and room tiles', (await pg.inner_text('#vch')) == '10' and (await pg.inner_text('#vrm')) == '1')
                ok('A8 header chip live', 'CH 10' in await pg.inner_text('#chip'))
                # the tracker starts once two readings (3 s apart) agree: give it a moment on a fast machine
                for _ in range(20):
                    xt = await pg.inner_text('#expt')
                    if '43.17%' in xt:
                        break
                    await pg.wait_for_timeout(1000)
                if '43.17%' not in xt:
                    print('  EXP tracker state:', ctl.exp.first, ctl.exp.last, ctl.settings.get('exp'), bool(ctl.scanner))
                ok(f'A8b the EXP card read the status bar (level 37, 43.17%) {xt[:60]!r}', '37' in xt and '43.17%' in xt and '93,499' in xt)
                await pg.click('#expreset'); await pg.wait_for_timeout(1500)
                ok('A8c Reset clears it (until the next readings)', ctl.exp.gained == 0 and ctl.exp.levels == 0)
                ok('A9 newest listings marked just listed', await pg.locator('#feed .fr.new').count() >= 6)
                await pg.screenshot(path=OUT + '_dark.png')
                ok('A9b the steps go away once listings are saved', await pg.locator('#steps').is_hidden())
                await pg.click('[data-nav=more]'); await pg.wait_for_timeout(500)
                ok('A9c Options: every setting is a card', await pg.locator('#app .ocards .oc').count() >= 8 and await pg.locator('#oa').count() == 1)
                await pg.check('#oq') ; await pg.uncheck('#oq'); await pg.wait_for_timeout(300)
                await pg.select_option('#om', '2'); await pg.wait_for_timeout(300)
                await pg.uncheck('#oa'); await pg.wait_for_timeout(300)
                st = json.load(open(os.path.join(work, 'settings.json')))
                ok('A10 options saved (chime off, screen 2, no auto start)', st['quiet'] is True and st['monitor'] == 2 and st['auto_start'] is False)
                on = await pg.is_checked('#odk')              # this browser asks for dark, so the switch starts on
                await pg.uncheck('#odk'); await pg.wait_for_timeout(200)
                lt = await pg.evaluate("document.documentElement.dataset.theme")
                await pg.check('#odk'); await pg.wait_for_timeout(200)
                ok(f'A10b the dark theme switch works (starts {on}, then {lt})', on and lt == 'light' and
                   await pg.evaluate("document.documentElement.dataset.theme") == 'dark')
                await pg.set_input_files('#opic', os.path.join(R, 'tests/fixtures/screw.png')); await pg.wait_for_timeout(6000)
                await pg.click('[data-nav=scan]'); await pg.wait_for_timeout(500)
                await pg.click('[data-chg=rm]'); await pg.fill('#irm', '7'); await pg.press('#irm', 'Enter'); await pg.wait_for_timeout(1500)
                ok('A11 room typed by hand', ctl.state['room'] == 7 and (await pg.inner_text('#vrm')) == '7')
                ok('A12 read a screenshot', 'screw.png: 6 listings' in await pg.inner_text('#notes'))
                await pg.click('[data-nav=browse]'); await pg.wait_for_timeout(1500)
                n = await pg.locator('#list [data-open]').count()
                ok(f'A12b Prices: one row per scanned item, no sample items ({n})', n == 24 and 'Purple Tube' not in await pg.inner_text('#list'))
                await pg.click('[data-ps=low]'); await pg.wait_for_timeout(300)
                first = (await pg.inner_text('#list [data-open] >> nth=0')).splitlines()[0]
                ok(f'A12c Cheapest first ({first})', first == 'Adamantium Ore')
                await pg.fill('#q', 'ore'); await pg.wait_for_timeout(300)
                ok('A12d search narrows the prices (the three ores)', await pg.locator('#list [data-open]').count() == 3)
                await pg.click('#list [data-open] >> nth=1'); await pg.wait_for_timeout(300)
                pn = await pg.inner_text('#ipanel')
                ok('A12e clicking a price card shows its details beside the cards', 'Where to buy' in pn and
                   (await pg.inner_text('#list [data-open][aria-pressed=true]')).splitlines()[0] in pn)
                await pg.click('[data-nav=market]'); await pg.wait_for_timeout(2500)
                rows = await pg.locator('#mb .fr').count(); mi = await pg.locator('#mb img.ic').count()
                ok(f'A13 listings: copies merged, each with its picture ({rows} rows, {mi} pictures)', rows == 17 and mi == 17)
                ok('A13b two copies show as x2', await pg.locator('#mb .cnt:has-text("×2")').count() == 3)
                ok('A14 market shows just listed', await pg.locator('#mb .fresh').count() >= 1)
                await pg.click('[data-lv=cards]'); await pg.wait_for_timeout(300)
                ok('A14b Cards view: the same listings as cards', await pg.locator('#mb.lcards > .card').count() == 17)
                await pg.click('[data-lv=compact]'); await pg.wait_for_timeout(300)
                await pg.screenshot(path=OUT + '_market.png')
                await pg.click('#mb [data-open]'); await pg.wait_for_timeout(500)
                ok('A15 item page has the big picture', await pg.locator('#app img.ic.lg').count() == 1)
                await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300)
                ok('A15e Esc goes back from an item', await pg.locator('#app img.ic.lg').count() == 0)
                await pg.click('[data-nav=more]'); await pg.keyboard.press('/'); await pg.wait_for_timeout(300)
                ok('A15f "/" jumps to the Prices search', await pg.evaluate("document.activeElement.id") == 'q')
                await pg.click('[data-nav=market]'); await pg.click('#mb [data-open]'); await pg.wait_for_timeout(500)
                ok('A15b item page says where to buy it', 'Where to buy' in await pg.inner_text('#app') and 'Cheapest NX <3' in await pg.inner_text('#app'))
                await pg.click('#back'); await pg.click('[data-nav=more]'); await pg.click('[data-go=deals]'); await pg.wait_for_timeout(300)
                ok('A15c More opens alerts and deals, with a way back', await pg.locator('#at').count() == 1 and
                   await pg.get_attribute('[data-nav=more]', 'aria-current') == 'page')
                await pg.click('#tomore'); await pg.click('[data-go=mine]'); await pg.wait_for_timeout(300)
                ok('A15d My shop has the post form', await pg.locator('#pgo').count() == 1)
                await pg.click('[data-nav=scan]'); await pg.wait_for_timeout(800)
                await pg.click('#go'); await pg.wait_for_timeout(1500)
                ok('A16 Stop stops', not ctl.state['watching'] and 'Start' in await pg.inner_text('#go'))
                ok('A16b stopping shops leaves EXP recording on', ctl.exp_runner is not None and (await pg.inner_text('#expgo')) == 'Stop')
                await pg.click('#expgo'); await pg.wait_for_timeout(1500)
                ok('A16c and EXP stops with its own button', ctl.exp_runner is None and (await pg.inner_text('#expgo')) == 'Start'
                   and json.load(open(os.path.join(work, 'settings.json')))['exp'] is False)
                ok('A17 feed kept after stop', await pg.locator('#feed .fr').count() == 29)
                await pg.reload(); await pg.wait_for_timeout(2000)
                ok('A18 reload restores the session feed', await pg.locator('#feed .fr').count() == 29)
            else:
                await pg.wait_for_timeout(500); await pg.screenshot(path=OUT + '_light.png')
                await pg.set_viewport_size({'width': 420, 'height': 900}); await pg.wait_for_timeout(500)
                sw = await pg.evaluate('document.documentElement.scrollWidth')
                ok(f'A19 phone width: no sideways scroll ({sw})', sw <= 420)
                await pg.screenshot(path=OUT + '_narrow.png', full_page=False)
            ok(f'A20 no page errors ({scheme}) {errs[:2]}', not errs)
            await ctx.close()
        await b.close()
asyncio.run(main())
srv.stop(); ctl.shutdown()
print('ALL APP CHECKS PASSED' if not fails else f'{len(fails)} FAILED')

sys.exit(1 if fails else 0)   # so a runner sees a failure, not just the printed line
