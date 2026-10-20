import os
import sys, os, time, json, tempfile, asyncio, urllib.request
R = sys.argv[1]; sys.path.insert(0, R)
work = tempfile.mkdtemp(prefix='mr_live_'); os.makedirs(os.path.join(work, 'scans'))
import shopreader.config as C; C.APP_DIR = work
import shopreader.market_server as M
M.APP_DIR = work
ALL = os.path.join(work, 'scans', 'all_scans.txt')
def stamp(dt=0):
    return time.strftime('@%Y-%m-%dT%H:%M:%S', time.localtime(time.time() - dt))
def add(lines):
    with open(ALL, 'a', encoding='utf-8') as f: f.write(''.join(l + '\n' for l in lines))
add([f'Bunny Ears | 62999 | Cheapest NX <3 | 1 | 10 | {stamp(600)}', f'Bunny Ears | 62999 | Cheapest NX <3 | 1 | 10 | {stamp(600)}',
     f'Ice Wand | 12500 | White Crusader Chainmail | 1 | 10 | {stamp(590)}'])
status = {'watching': True, 'channel': 10, 'room': 1, 'total': 3, 'shop': 'Cheapest NX <3'}
srv = M.MarketServer(lambda: status); url = srv.start(); print('url', url)
fails = []
def ok(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond: fails.append(name)
# Host check
req = urllib.request.Request(url + 'api/rows?from=0', headers={'Host': 'evil.example:8765'})
try: urllib.request.urlopen(req); ok('L0 other hosts refused', False)
except urllib.error.HTTPError as e: ok('L0 other hosts refused', e.code == 403)
# a second server finds the first instead of stealing the port
srv2 = M.MarketServer(); u2 = srv2.start(); ok('L0b second copy reuses the running market', u2 == url and srv2.shared)
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({'executable_path': os.environ['PW_CHROMIUM']} if os.environ.get('PW_CHROMIUM') else {}))
        ctx = await b.new_context(viewport={'width': 1100, 'height': 900})
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(url); await pg.wait_for_timeout(1500)
        listings = lambda: pg.evaluate("() => window.App.analyze().rows.filter(o=>o.st==='sale').length")
        n = await listings(); ok(f'L1 page imports all_scans.txt by itself ({n} for sale)', n == 3)
        ok('L2 no sample data in live mode', await pg.evaluate("() => window.App.S.listings.length") == 0)
        banner = await pg.inner_text('#chip'); ok('L3 header chip shows live status: ' + banner[:90], 'CH 10' in banner and 'FM 1' in banner)
        add([f'Mithril Maul | 9000 | White Crusader Chainmail | 1 | 10 | {stamp()}'])
        await pg.wait_for_timeout(3000)
        ok('L4 a new row appears within 3 s, no importing', await listings() == 4)
        ok('L5 the Market list shows it', 'Mithril Maul' in await pg.inner_text('#mb'))
        # half-written line is not read until complete
        with open(ALL, 'a', encoding='utf-8') as f: f.write('Blue Axe | 11000 | White Crus')
        await pg.wait_for_timeout(2500)
        ok('L6 half-written line waits', await listings() == 4)
        with open(ALL, 'a', encoding='utf-8') as f: f.write(f'ader Chainmail | 1 | 10 | {stamp()}\n')
        await pg.wait_for_timeout(2500)
        ok('L7 then arrives complete', await listings() == 5)
        await pg.reload(); await pg.wait_for_timeout(2500)
        ok('L8 reload: nothing doubled', await listings() == 5)
        await pg.screenshot(path=sys.argv[2])
        # MapleReader closed: banner says so; reopened: carries on
        srv.stop(); await pg.wait_for_timeout(3000)
        ok('L9 app closed: chip says so', 'closed' in await pg.inner_text('#chip'))
        url2 = srv.start(); ok('L9b same address after restart', url2 == url)
        add([f'Dankke | 15000 | White Crusader Chainmail | 1 | 10 | {stamp()}'])
        await pg.wait_for_timeout(3000)
        ok('L10 app back: rows flow again', await listings() == 6)
        # all_scans.txt deleted and started fresh
        os.remove(ALL); add([f'Red Potion | 50 | Potion Shop | 2 | 3 | {stamp()}'])
        await pg.wait_for_timeout(3000)
        n = await listings(); ok(f'L11 new all_scans.txt after deleting the old: kept old + added new ({n})', n == 7)
        # Reload all: clears and rereads the file
        await pg.click('summary:has-text("Older scan files")'); await pg.click('#reload'); await pg.wait_for_timeout(3000)
        n = await listings(); ok(f'L12 Reload all rebuilds from the file ({n})', n == 1)
        # big file
        big = [f'Bulk {i % 50} | {100 + i} | Shop {i % 40} | {1 + i % 11} | {1 + i % 20} | {stamp(3000 - i // 20)}' for i in range(20000)]
        add(big); t = time.time()
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await listings() >= 20001: break
        ok(f'L13 20,000 rows arrive ({await listings()}) in {time.time() - t:.0f} s', await listings() == 20001)
        ok('L14 no page errors ' + str(errs[:2]), not errs)
        await b.close()
asyncio.run(main())
print('ALL LIVE CHECKS PASSED' if not fails else f'{len(fails)} FAILED')
