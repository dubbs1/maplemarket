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
    tracker()
    loop()
    print()
    print('EXP tracker: all checks passed.' if not fails else f'EXP tracker: {len(fails)} FAILED')
    sys.exit(1 if fails else 0)
