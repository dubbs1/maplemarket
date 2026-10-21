"""Checks the EXP tracker: reading the status bar, and turning readings into EXP per hour.

1. The six test pictures with a status bar (three at the usual interface size, three at others: 0.9, 0.95, 1.14)
   read EXP 93,499, 43.17% and level 37; the owner's bar at level 38 reads 36,420, 15.14%, 38.
2. The same bar shrunk or grown (0.75x to 1.9x, two ways of resizing) is read right or skipped, never wrong.
3. A picture without a status bar finds none.
4. The tracker: starts when two readings agree, adds up gains, drops a misread, counts a death's loss and a level-up,
   works out EXP per hour and the time to the next level.
5. EXP is recorded on its own, apart from the shop scanner (pretend screenshots, as in test_session.py).
"""
import os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image                                       # noqa: E402
from shopreader import exp as E                             # noqa: E402
from shopreader.ocr import find_tesseract                   # noqa: E402

FX = os.path.join(HERE, 'fixtures')
TRUE = (93499, 43.17, 37)
fails = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        fails.append(what)


def load(name):
    return Image.open(os.path.join(FX, name)).convert('RGB')


def read(img):
    w = E.ExpWatcher()
    r = w.update(img, now=1000)
    return r and (r['exp'], r['pct'], r['level'])


def pictures():
    print('Status bars in the test pictures:')
    for name in ('live_shop.png', 'desk_live.png', 's711.png', 'ch2.png', 'live_ch.png', 'shopS.png'):
        img = load(name)
        bar = E.find_bar(img)
        got = read(img)
        check(got == TRUE, f'{name} (size {bar["size"]:.2f}): {got}')
    got = read(load('status38.png'))
    check(got == (36420, 15.14, 38), f'status38.png (your bar at level 38, with 5s and an 8): {got}')
    got = read(load('status38_lowmp.png'))
    check(got == (80101, 33.31, 38), f'status38_lowmp.png (HP 1146/1325, MP 471/1089: the MP bar drawn dark): {got}')
    check(E.find_bar(load('allsold.png')) is None, 'allsold.png: no status bar (a shop picture without one)')


def sizes():
    print('The status bar at other interface sizes:')
    base = load('live_shop.png')
    for f in (0.75, 0.85, 0.9, 1.15, 1.3, 1.6, 1.9):
        right = wrong = 0
        for dx in (0, 1):
            for flt in (Image.BILINEAR, Image.LANCZOS):
                im = base.crop((dx, dx, base.width, base.height))
                got = read(im.resize((round(im.width * f), round(im.height * f)), flt))
                if got:
                    right += got[:2] == TRUE[:2]
                    wrong += got[:2] != TRUE[:2] or got[2] not in (None, TRUE[2])
        check(wrong == 0 and right >= 3, f'x{f}: {right} of 4 read right, {wrong} wrong')


def low_bars():
    print('HP and MP not full, the EXP line covered for a while:')
    from PIL import ImageDraw
    base = load('live_shop.png')
    bar = E.find_bar(base)
    hp, mp = bar['hp'], bar['mp']
    for f in (0.8, 1.0, 1.3):
        for hp_left, mp_left, mp_col in ((0.5, 0.2, (52, 52, 52)), (0.9, 0.6, (0, 46, 70)), (0.3, 0.9, (52, 52, 52))):
            im = base.copy()
            d = ImageDraw.Draw(im)
            d.rectangle((hp[0] + int((hp[2] - hp[0]) * hp_left), hp[1], hp[2], hp[3]), fill=(191, 173, 172))  # HP used up
            if mp_col == (0, 46, 70):                                       # low MP: the fill drawn dark navy
                d.rectangle((mp[0], mp[1], mp[0] + int((mp[2] - mp[0]) * mp_left), mp[3]), fill=mp_col)
            d.rectangle((mp[0] + int((mp[2] - mp[0]) * mp_left), mp[1], mp[2], mp[3]), fill=(52, 52, 52))     # MP used up
            if f != 1:
                im = im.resize((round(im.width * f), round(im.height * f)), Image.BILINEAR)
            got = read(im)
            check(got and got[:2] == TRUE[:2], f'x{f}, HP {hp_left:.0%} MP {mp_left:.0%} full: {got}')
    w = E.ExpWatcher()
    first = w.update(base, now=1000)
    covered = base.copy()
    ImageDraw.Draw(covered).rectangle((bar['label'][2], bar['line'][0], bar['label'][2] + 300, bar['line'][1]), fill=(0, 0, 0))
    no_mp = covered.copy()
    ImageDraw.Draw(no_mp).rectangle(mp, fill=(52, 52, 52))                  # and MP all gone: the bar can't be found again
    for i in range(8):
        w.update(no_mp, now=1003 + i * 3)
    back = base.copy()
    ImageDraw.Draw(back).rectangle(mp, fill=(52, 52, 52))
    again = w.update(back, now=1100)
    check(first and again and again['exp'] == TRUE[0], 'covered for a while with MP gone: keeps reading where the bar was')


def tracker():
    print('The tracker:')
    t = E.ExpTracker()
    need = 216580                                           # EXP this level needs
    r = lambda exp, lv=37: {'exp': exp, 'pct': round(exp * 100 / need, 2), 'level': lv}
    check(not t.add(r(93499), now=0) and t.summary() is None, 'one reading alone does not start it')
    check(t.add(r(93499), now=3) and t.summary()['gained'] == 0, 'a second agreeing reading starts it')
    t.add(r(94000), now=60)
    t.add(r(95000), now=120)
    s = t.summary(now=120)
    check(s['gained'] == 1501, f'gains add up: {s["gained"]}')
    check(abs(s['per_hour'] - 1501 * 30) < 50, f'EXP per hour: {s["per_hour"]}')
    check(abs(s['need'] - need) < need * 0.001 and s['left'] == s['need'] - 95000, f'EXP to the next level: {s["left"]}')
    check(s['eta'] and abs(s['eta'] - s['left'] / s['per_hour'] * 3600) < 2, f'time to the next level: {s["eta_text"]}')
    check(not t.add({'exp': 35000, 'pct': 44.0, 'level': 37}, now=123), 'a misread (number and % disagree) is dropped')
    check(t.add(r(90000), now=130) and t.summary()['lost'] == 5000, 'EXP lost from dying is counted apart')
    t.add(r(216000), now=200)
    up = t.add({'exp': 1200, 'pct': 0.5, 'level': 38}, now=210)
    s = t.summary(now=210)
    check(up and s['levels'] == 1 and s['level'] == 38, f'level-up seen: level {s["level"]}, {s["levels"]} up')
    expect = 1501 + 126000 + (need - 216000) + 1200         # (the level's EXP is known to within the % rounding)
    check(abs(s['gained'] - expect) < 20, f'gains carry over the level-up: {s["gained"]} (about {expect})')
    t2 = E.ExpTracker()
    t2.add(r(50000), now=0)
    t2.add(r(50000), now=3)
    t2.add(r(200000), now=60)
    check(t2.add({'exp': 4000, 'pct': 1.23, 'level': None}, now=70) and t2.summary()['levels'] == 1,
          'level-up seen without reading the level (the % drops and the level needs more EXP)')
    t3 = E.ExpTracker()
    t3.add(r(150000), now=0)
    t3.add(r(150000), now=3)
    check(t3.add({'exp': 140000, 'pct': round(140000 * 100 / need, 2), 'level': 38}, now=10) and
          t3.summary()['levels'] == 0 and t3.summary()['lost'] == 10000, 'a death with the level misread is not a level-up')
    t4 = E.ExpTracker()                                     # just after a level-up the level's EXP is learnt again
    t4.add(r(200000), now=0)
    t4.add(r(200000), now=3)
    t4.add({'exp': 50, 'pct': 0.05, 'level': 38}, now=10)          # levelled up (too small a % to know the new level)
    t4.add({'exp': 3000, 'pct': 2.0, 'level': 38}, now=20)
    check(not t4.add({'exp': 93000, 'pct': 2.1, 'level': 38}, now=30), 'a misread just after a level-up is dropped')
    t5 = E.ExpTracker()                                     # your own readings (October 20): 36,420 of 240,500 at level 38
    for i, (x, p) in enumerate(((36420, 15.14), (36420, 15.14), (36450, 15.16), (36475, 15.17))):
        t5.add({'exp': x, 'pct': p, 'level': 38}, now=i * 30)
    t5.add({'exp': 36500, 'pct': 15.18, 'level': 33}, now=150)   # a level misread later on
    s5 = t5.summary(now=150)
    check(s5['gained'] == 80 and abs(s5['need'] - 240500) < 240500 * 0.002 and s5['level'] == 38,
          f'your readings: gained {s5["gained"]}, level needs {s5["need"]} (the game says 240,500), level {s5["level"]}')
    t.reset()
    check(t.summary() is None, 'Reset clears it')


def hours_and_days():
    print('The EXP page: 10-minute slots, the last hour against the one before, the best hour, each day\'s total:')
    import tempfile
    gains = []
    t = E.ExpTracker(on_gain=lambda n, at: gains.append(n))
    need = 240500
    r = lambda x: {'exp': x, 'pct': round(x * 100 / need, 2), 'level': 38}
    t.add(r(50000), now=0)
    t.add(r(50000), now=3)
    s = t.summary(now=30)
    check(s['slots'] == [0] and s['hour'] is None and s['best_hour'] is None, f'just started: {s["slots"]}, no hours yet')
    x = 50000
    for i in range(1, 151):                                 # 2.5 hours: 200 EXP a minute, then 300
        x += 200 if i <= 60 else 300
        t.add(r(x), now=3 + i * 60)
    s = t.summary(now=3 + 150 * 60)
    check(s['slots'] == [2000] * 3 + [3000] * 9, f'the last 2 hours in 10-minute slots: {s["slots"]}')
    check((s['hour'], s['prev_hour'], s['best_hour']) == (18000, 15000, 18000),
          f'last hour {s["hour"]}, the hour before {s["prev_hour"]}, best hour {s["best_hour"]}')
    check(sum(gains) == s['gained'] == 39000, f'every gain goes to the day\'s total: {sum(gains)}')
    end = 3 + 150 * 60
    t.pause(now=end)
    later = t.summary(now=end + 2 * 3600)
    check((later['per_hour'], later['minutes'], later['slots'], later['hour']) == (s['per_hour'], s['minutes'], s['slots'], s['hour'])
          and not t.add(r(x + 500), now=end + 60), f'Stop: the numbers stay as they were two hours later ({later["per_hour"]}/h, '
          f'{later["minutes"]} min), and readings wait')
    t.resume(now=end + 2 * 3600)
    for i in range(1, 11):
        t.add(r(x + i * 300), now=end + 2 * 3600 + i * 60)
    s2 = t.summary(now=end + 2 * 3600 + 600)
    check(s2['minutes'] == s['minutes'] + 10 and s2['slots'][-1] == 3000 and s2['hour'] == 18000 and s2['per_hour'] == 18000,
          f'Start again: the stopped time is left out ({s2["minutes"]} min, last 10 min {s2["slots"][-1]}, {s2["per_hour"]}/h)')
    path = os.path.join(tempfile.mkdtemp(prefix='maplereader_expdays_'), 'scans', 'exp_days.json')
    d = E.ExpDays(path)
    day = 86400
    noon = day // 2                                         # (midday, so any time zone keeps the same dates)
    d.add(1000, now=10 * day + noon)
    d.add(500, now=12 * day + noon)
    d.add(-5, now=12 * day + noon + 10)
    d.flush()
    last = E.ExpDays(path).last(3, now=12 * day + noon + 50)
    check([x['gained'] for x in last] == [1000, 0, 500], f'the last 3 days, kept in scans/exp_days.json: {last}')
    check(E.ExpDays(path).days and sum(E.ExpDays(path).days.values()) == 1500, 'the totals survive a restart (losses never count)')


def breaks_and_log():
    print('Breaks (no EXP for a minute) and the EXP log:')
    import tempfile
    runs = []
    t = E.ExpTracker(on_run=runs.append)
    need = 240500
    r = lambda x, lv=38: {'exp': x, 'pct': round(x * 100 / need, 2), 'level': lv}
    t.add(r(50000), now=0)
    t.add(r(50000), now=3)
    t.set_map('The Land of Wild Boar II', now=3)
    x = 50000
    for i in range(1, 31):                                  # 30 minutes hunting: 300 EXP a minute
        x += 300
        t.add(r(x), now=3 + i * 60)
    s = t.summary(now=1803 + 600)                           # then 10 minutes in town
    check(s['idle'] and s['minutes'] == 31 and s['per_hour'] > 15000, f'10 minutes without EXP: paused at 31 min, {s["per_hour"]}/h')
    for i in range(1, 11):                                  # back hunting
        x += 300
        t.add(r(x), now=2403 + i * 60)
    s = t.summary(now=2403 + 600)
    check(not s['idle'] and s['minutes'] == 40 and s['per_hour'] == 18000 and s['last5'] == 18000,
          f'back: the break is left out ({s["minutes"]} min, {s["per_hour"]}/h, last 5 min {s["last5"]}/h)')
    check(not runs and s['run']['map'] == 'The Land of Wild Boar II' and s['run']['gained'] == 12000,
          f'a short break keeps the same EXP log entry ({s["run"]})')
    for i in range(1, 6):                                   # after a 2-hour break, 5 more minutes (the minute
                                                            # of waiting before the pause counts)
        x += 300
        t.add(r(x), now=2403 + 600 + 7200 + i * 60)
    check(len(runs) == 1 and runs[0]['minutes'] == 41 and runs[0]['gained'] == 12000 and runs[0]['map'] == 'The Land of Wild Boar II',
          f'a long break ends the entry: {runs and {k: runs[0][k] for k in ("minutes", "gained", "per_hour", "level", "map")}}')
    t.set_map('Ant Tunnel I', now=2403 + 600 + 7200 + 330)
    check(len(runs) == 2 and runs[1]['gained'] == 1500 and t.summary(now=2403 + 600 + 7200 + 330)['run']['map'] == 'Ant Tunnel I',
          'a new map starts a new entry')
    t.add(r(x + 300), now=2403 + 600 + 7200 + 390)
    t.add({'exp': 3000, 'pct': 1.2, 'level': 39}, now=2403 + 600 + 7200 + 450)
    check(len(runs) == 3 and runs[2]['level'] == 38 and t.summary(now=2403 + 600 + 7200 + 450)['run']['level'] == 39,
          'a level-up starts a new entry at the new level')
    path = os.path.join(tempfile.mkdtemp(prefix='maplereader_explog_'), 'scans', 'exp_log.json')
    log = E.ExpLog(path)
    for e in runs:
        log.add(e)
    first = log.list()[0]
    check(log.rename(first['id'], '  Boars with Sam  ') and E.ExpLog(path).list()[0]['name'] == 'Boars with Sam', 'a line can be renamed (kept)')
    check(log.delete(first['id']) and len(E.ExpLog(path).list()) == 2 and not log.delete('nope'), 'and deleted')


def map_and_party():
    print('The map\'s name and the party, for the EXP log:')
    from shopreader import location as L
    hunt = load('hunt_party.png')                            # your screenshot: a party of 4 in a party quest
    check(L.read_map(hunt) == '1st Accompaniment <1st Stage>', f'hunt_party.png: the map is {L.read_map(hunt)!r}')
    check(L.read_map(load('kerning_inv.png')) == 'Kerning City', f"kerning_inv.png: {L.read_map(load('kerning_inv.png'))!r} (once read 'Kerming')")
    check(L.read_map(load('live_ch.png')) is None, 'live_ch.png (a window over the minimap): no name rather than a wrong one')
    check(L.party_size(hunt) == 4, f'hunt_party.png: a party of {L.party_size(hunt)} (MYK3, RuneKnight, Natsumi, Cashern)')
    for name in ('live_shop.png', 'desk_live.png', 's711.png', 'ch2.png', 'shopS.png'):
        img = load(name)
        check(L.read_map(img) == 'Free Market <1>' and L.party_size(img) is None,
              f'{name}: {L.read_map(img)!r}, no party (the red skill icons are not one)')
    t = E.ExpTracker(on_run=lambda e: runs.append(e))
    runs = []
    need = 240500
    r = lambda x: {'exp': x, 'pct': round(x * 100 / need, 2), 'level': 38}
    t.add(r(50000), now=0)
    t.add(r(50000), now=3)
    t.set_map('1st Accompaniment <1st Stage>', now=3)
    t.set_party(4)
    for i in range(1, 6):
        t.add(r(50000 + i * 500), now=3 + i * 60)
    t.set_map('Free Market <1>', now=400)
    check(len(runs) == 1 and runs[0]['map'] == '1st Accompaniment <1st Stage>' and runs[0]['party'] == 4,
          f'the EXP log line keeps the map and the party ({runs and runs[0]})')


def mesos():
    print('Mesos (the Item window\'s meso box):')
    from shopreader import mesos as M
    inv = load('kerning_inv.png')                            # your screenshot: 1,421,566 mesos, level 39
    got = [M.read_mesos(inv.resize((round(inv.width * f), round(inv.height * f)), flt))
           for f in (0.8, 1.0, 1.3, 1.6) for flt in (Image.BILINEAR, Image.LANCZOS)]
    check(got == [1421566] * 8, f'kerning_inv.png at 0.8x to 1.6x: {set(got)}')
    check(read(inv) == (16709, 6.27, 39), f'and its EXP line, with the level tiles\' 9: {read(inv)}')
    others = [n for n in ('live_shop.png', 'desk_live.png', 'ch2.png', 'shopS.png', 'hunt_party.png', 'live_ch.png') if M.find_box(load(n))]
    check(not others, f'no meso box where the Item window isn\'t open (a shop sign\'s gold frame is not a coin) {others}')
    t = E.ExpTracker(on_run=lambda e: runs.append(e))
    runs = []
    need = 240500
    r = lambda x: {'exp': x, 'pct': round(x * 100 / need, 2), 'level': 39}
    t.set_mesos(1_000_000, now=0)
    t.add(r(50000), now=0)
    t.add(r(50000), now=3)
    for i in range(1, 11):                                  # 10 minutes: 600 mesos a minute, one shop visit (-5,000)
        t.add(r(50000 + i * 500), now=3 + i * 60)
        t.set_mesos(1_000_000 + i * 600 - (5000 if i >= 6 else 0), now=3 + i * 60)
    t.set_mesos(99_000_000, now=3 + 630)                    # a misread
    s = t.summary(now=3 + 630)
    check(s['mesos'] == 1_001_000 and s['mesos_gained'] == 5400 and s['mesos_per_hour'] == 36000,      # (the minute of the
          f'gained {s["mesos_gained"]} (spending not taken off, a misread jump ignored), {s["mesos_per_hour"]}/h')   # spend shows -4,400)
    t.end_run(now=3 + 630)
    check(runs and runs[0]['mesos'] == 5400 and runs[0]['mesos_per_hour'] == 36000, f'the EXP log line has mesos/h: {runs and runs[0]}')


def loop():
    print('EXP is recorded on its own (no shop watching needed):')
    pics = [load('live_shop.png')] * 4

    class Shot:
        def __init__(s, img):
            s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')

    class Screen:
        monitors = [{}, {}]
        def __enter__(s): return s
        def __exit__(s, *a): pass
        def grab(s, mon):
            if not pics:
                sc.stop()
                return Shot(Image.new('RGB', (64, 64)))
            return Shot(pics.pop(0))

    sys.modules['mss'] = types.SimpleNamespace(MSS=lambda: Screen())
    from shopreader import scanner
    clock = [1000.0]
    scanner.time = types.SimpleNamespace(sleep=lambda s: clock.__setitem__(0, clock[0] + 4), time=lambda: clock[0])
    E.time = scanner.time                                    # the watcher's "every few seconds" uses the same clock
    seen = []

    class Ev(scanner.Events):
        def message(self, text): pass
        def exp(self, summary): seen.append(summary)

    t = E.ExpTracker()
    work = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'maplereader_exp_test')
    os.makedirs(work, exist_ok=True)
    old = os.getcwd()
    os.chdir(work)
    try:
        sc = scanner.ExpRunner(t, events=Ev(), every=0)
        sc.run()
    finally:
        os.chdir(old)
    s = t.summary()
    check(bool(seen) and s and (s['exp'], s['pct'], s['level']) == TRUE, f'the EXP recorder got {s and (s["exp"], s["pct"], s["level"])}')
    import inspect
    check('exp' not in inspect.signature(scanner.Scanner).parameters, 'the shop scanner doesn\'t read EXP (they are separate)')


if __name__ == '__main__':
    if not find_tesseract():
        sys.exit('Tesseract not found')
    pictures()
    sizes()
    low_bars()
    tracker()
    hours_and_days()
    breaks_and_log()
    map_and_party()
    mesos()
    loop()
    print()
    print('EXP tracker: all checks passed.' if not fails else f'EXP tracker: {len(fails)} FAILED')
    sys.exit(1 if fails else 0)
