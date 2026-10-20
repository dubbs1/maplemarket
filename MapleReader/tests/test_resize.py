"""The game window is resized in the middle of a session, and the game draws its interface at other sizes.

Plays pretend screenshots through the real watching loop: a shop at the usual size, then the same shop after the
window was made smaller (the picture shrunk the way Windows does it), then other shops drawn smaller and bigger.
Every saved name must be a real one, and the shop seen at two sizes must not be saved twice.
Run with run_tests.bat (or: py -3.13 tests/test_resize.py).
"""
import glob, io, os, sys, tempfile, time, types
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw                        # noqa: E402

FX = os.path.join(HERE, 'fixtures')


def load(name):
    return Image.open(os.path.join(FX, name)).convert('RGB')


def resized(im, f, at=(80, 50)):
    """The same screen after the game window became f times as big: the picture scaled, on a dark desktop."""
    small = im.resize((round(im.width * f), round(im.height * f)), Image.BILINEAR)
    out = Image.new('RGB', im.size, (24, 26, 30))
    out.paste(small.crop((0, 0, min(small.width, im.width - at[0]), min(small.height, im.height - at[1]))), at)
    return out


def expected(name):
    return sorted(tuple(x.strip() for x in ln.split('|')[:2]) + ('sold' in ln,) for ln in
                  open(os.path.join(FX, 'expected', name + '.txt'), encoding='utf-8') if ln.count('|') >= 4)


def frames():
    ch = load('live_ch.png')
    wcc, shop, s711 = load('wcc_full.png').resize(ch.size), load('live_shop.png'), load('s711.png').resize(ch.size)
    noshop = ch.copy()
    ImageDraw.Draw(noshop).rectangle((490, 440, 1390, 700), fill=(120, 170, 220))   # map with no window open
    seq = ([noshop] * 2 + [ch] * 3 +                    # the Change Channel window: channel 10
           # a shop, then the window made smaller while it's open, shrinking around the list, which stays about
           # where it was (the case where the reader must notice the rows changed size)
           [wcc] * 3 + [resized(wcc, 0.8, (round(756 * 0.2), round(684 * 0.2)))] * 4 +
           [noshop] * 2 + [resized(shop, 0.75)] * 3 +   # another shop at the smaller size
           [noshop] * 2 + [resized(s711, 1.3, (0, 0))] * 3 + [noshop] * 2)   # one drawn bigger
    out = []
    for i, f in enumerate(seq):                         # a small moving sprite, so the screen is never perfectly still
        f = f.copy()
        ImageDraw.Draw(f).rectangle((1500 + i % 9 * 7, 300, 1540 + i % 9 * 7, 360), fill=(200, 50, 50))
        out.append(f)
    return out


def main():
    pics = frames()

    class Shot:
        def __init__(s, img):
            s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')

    class Screen:
        monitors = [{}, {}]
        def __enter__(s): return s
        def __exit__(s, *a): pass
        def grab(s, mon):
            if not pics:
                raise KeyboardInterrupt                 # out of pictures: end the session
            return Shot(pics.pop(0))

    sys.modules['mss'] = types.SimpleNamespace(MSS=lambda: Screen())
    sys.stdin = io.StringIO('')
    from shopreader import session
    time.sleep = lambda s: None
    work = tempfile.mkdtemp(prefix='maplereader_resize_')
    old = os.getcwd()
    os.chdir(work)
    try:
        session.main(['--quiet'])
    except KeyboardInterrupt:
        pass
    finally:
        os.chdir(old)
    files = glob.glob(os.path.join(work, 'scans', 'scan_*.txt'))
    lines = open(files[0], encoding='utf-8').read().splitlines() if files else []
    print('\n'.join(lines))
    by_shop = {}
    for ln in lines:
        p = [x.strip() for x in ln.split('|')]
        by_shop.setdefault(p[2], []).append((p[0], p[1], 'sold' in p[5:]))
    fails = []

    def check(name, shop, want, allow_missing=0):
        got, want = Counter(by_shop.get(shop, [])), Counter(want)
        extra = list((got - want).elements())             # misread, or a copy saved that isn't there
        missing = sum((want - got).values())
        ok = not extra and missing <= allow_missing
        print(('ok     ' if ok else 'FAILED ') + f'{name}: {sum(got.values())} saved, {len(extra)} wrong or extra, ' +
              f'{missing} missed' + (f' {extra[:3]}' if extra else ''))
        if not ok:
            fails.append(name)
    check('a shop, then the window made smaller while it is open: no misreads, nothing saved twice',
          'White Crusader Chainmail', expected('wcc.png'))
    check('a shop drawn at 75% size', 'Cheapest NX <3', expected('live_shop.png'), allow_missing=1)
    check('a shop drawn at 130% size', '711', expected('s711.png'), allow_missing=1)
    # single pictures at other interface sizes (the game's "UI Size", full screen at a lower resolution)
    from shopreader import rows as RW, title
    for f in (0.75, 1.6, 1.875):
        good = want_n = 0
        for name in ('wcc.png', 'live_shop.png', 's711.png', 'gfa.png', 'allsold.png'):
            im = load(name)
            im = im.resize((round(im.width * f), round(im.height * f)), Image.BILINEAR)
            title.TITLE_CACHE.clear()
            RW.ROW_CACHE.clear()
            got = Counter((r['item'], str(r['each']), bool(r.get('sold'))) for r in RW.parse_frame(im, [])[0])
            want = Counter(expected(name))
            good, want_n = good + sum((got & want).values()), want_n + sum(want.values())
        ok = good >= 0.85 * want_n
        print(('ok     ' if ok else 'FAILED ') + f'pictures drawn at {f:.0%} size: {good} of {want_n} listings read right')
        if not ok:
            fails.append(f'size {f}')
    # a shop whose visible rows are all sold, with its window anywhere on screen: the list is found by its faded
    # block, whose measured size depends on where it falls on the colour search's grid
    sold = load('allsold.png')
    want = Counter(expected('allsold.png'))
    misses = []
    for x0 in range(330, 354, 4):
        for y0 in range(70, 94, 6):
            RW.ROW_CACHE.clear()
            got = Counter((r['item'], str(r['each']), bool(r.get('sold')))
                          for r in RW.parse_frame(sold.crop((x0, y0, 1160, 800)), [])[0])
            if got != want:
                misses.append((x0, y0))
    print(('ok     ' if not misses else 'FAILED ') + f'an all-sold shop at 24 window positions: {24 - len(misses)} read right' +
          (f' (missed at {misses[:4]})' if misses else ''))
    if misses:
        fails.append('all-sold positions')
    real = set(by_shop) <= {'White Crusader Chainmail', 'Cheapest NX <3', '711'}
    print(('ok     ' if real else 'FAILED ') + f'every shop name is a real one {sorted(by_shop)}')
    if not real:
        fails.append('shop names')
    print('RESIZE CHECK PASSED' if not fails else 'RESIZE CHECK FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
