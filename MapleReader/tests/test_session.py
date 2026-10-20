"""Plays a pretend game session (a series of screenshots) through the real watching loop.

No game needed: a fake screen hands the reader pictures from tests/fixtures one at a time:
the Change Channel window, then several shops (some with sold rows), with map views between.
Checks the reader picks up channel 10 and room 1 and saves the expected 29 listings.
"""
import glob, io, os, re, sys, tempfile, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw                        # noqa: E402

FX = os.path.join(HERE, 'fixtures')
EXPECTED_LINES = 29


def load(name, size=None):
    im = Image.open(os.path.join(FX, name)).convert('RGB')
    return im.resize(size) if size else im


def frames():
    shop = load('live_shop.png')
    size = shop.size
    noshop = load('live_ch.png').copy()
    ImageDraw.Draw(noshop).rectangle((490, 440, 1390, 700), fill=(120, 170, 220))   # map with no window open
    ch2, s711, shopS = load('ch2.png', size), load('s711.png', size), load('shopS.png', size)
    wcc, cov, full = load('wcc_full.png', size), load('sold2_cov.png', size), load('sold2_full.png', size)
    seq = ([noshop] * 2 + [ch2] * 3 + [s711] * 3 + [noshop] * 2 + [shopS] * 3 + [noshop] * 4 + [wcc] * 3 +
           [noshop] * 3 + [cov] * 3 + [full] * 3 + [noshop] * 2 + [shop] * 3 + [noshop] * 2)
    out = []
    for i, f in enumerate(seq):                         # a small moving sprite, so the screen is never perfectly still
        f = f.copy()
        k = i % 9
        ImageDraw.Draw(f).rectangle((1500 + k * 7, 300, 1540 + k * 7, 360), fill=(200, 50, 50))
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
    time.sleep = lambda s: None                   # no waiting between pretend screenshots
    work = tempfile.mkdtemp(prefix='maplereader_test_')
    old = os.getcwd()
    os.chdir(work)
    try:
        session.main(['--quiet'])
    except KeyboardInterrupt:
        pass
    finally:
        os.chdir(old)
    everything = os.path.join(work, 'scans', 'all_scans.txt')
    files = glob.glob(os.path.join(work, 'scans', 'scan_*.txt'))
    lines = open(files[0], encoding='utf-8').read().splitlines() if files else []
    print('\n'.join(lines))
    fails = []
    if len(lines) != EXPECTED_LINES:
        fails.append(f'expected {EXPECTED_LINES} listings, got {len(lines)}')
    parts = [ln.split(' | ') for ln in lines]
    if any(p[4] != '10' for p in parts):
        fails.append('channel should be 10 on every line')
    if any(p[3] != '1' for p in parts):
        fails.append('room should be 1 on every line')
    if any(not re.fullmatch(r'@\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d', p[-1]) for p in parts):
        fails.append('every line should end with the time it was seen (@2026-10-19T09:41:05)')
    pics_dir = os.path.join(work, 'scans', 'icons')
    got_icons = set(f[:-4] for f in os.listdir(pics_dir) if f.endswith('.png')) if os.path.isdir(pics_dir) else set()
    from shopreader.icons import slug
    missing = {slug(p[0]) for p in parts} - got_icons
    if missing:
        fails.append('item pictures missing for: ' + ', '.join(sorted(missing)))
    if not os.path.isfile(everything) or open(everything, encoding='utf-8').read().splitlines() != lines:
        fails.append('all_scans.txt should hold the same lines as the session file')
    print()
    for f in fails:
        print('FAILED:', f)
    print('SESSION CHECK PASSED' if not fails else 'SESSION CHECK FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    t = time.time()
    code = main()
    print(f'({round(time.time() - t)} s)')
    sys.exit(code)
