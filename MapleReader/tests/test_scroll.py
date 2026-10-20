"""Scrolling through a long shop full of identical listings must save every row exactly once.

Builds a pretend 20-row shop from tests/fixtures/screw.png (14 x "Screw, 1 for 299 mesos", one of them a
stack of 46) and ilu.png (6 different items), moves the scrollbar handle like the game does, and plays
the screenshots through the real watching loop.
"""
import collections, glob, io, os, sys, tempfile, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image                                   # noqa: E402

FX = os.path.join(HERE, 'fixtures')
SCREW_Y = [276, 338, 401, 463, 526, 588]              # row centres in screw.png
ILU_Y = [281, 343, 406, 468, 531, 593]                # row centres in ilu.png (list 7 px further right)
SB_X, SB_TOP, SB_FREE, HANDLE = (324, 349), 259, 292, (406, 446)


def build(kinds):
    base = Image.open(os.path.join(FX, 'screw.png')).convert('RGB')
    ilu = Image.open(os.path.join(FX, 'ilu.png')).convert('RGB')
    src = {'S100': (base, SCREW_Y[0], 0), 'S46': (base, SCREW_Y[5], 0)}
    for i, y in enumerate(ILU_Y):
        src['I%d' % i] = (ilu, y, 7)
    handle = base.crop((SB_X[0], HANDLE[0], SB_X[1], HANDLE[1]))
    track = base.crop((SB_X[0], 500, SB_X[1], 501))

    def frame(off, extra_px=0):
        im = base.copy()
        for j in range(6):
            top = SCREW_Y[j] - 35
            hgt = (SCREW_Y[j + 1] - 35 if j < 5 else SCREW_Y[5] + 27) - top
            pic, y, dx = src[kinds[off + j]]
            im.paste(pic.crop((5 + dx, y - 35, 320 + dx, y - 35 + hgt)), (5, top))
        for y in range(SB_TOP, SB_TOP + SB_FREE + 40):
            im.paste(track, (SB_X[0], y))
        pos = SB_TOP + round(off * SB_FREE / (len(kinds) - 6)) + extra_px
        im.paste(handle, (SB_X[0], pos))
        return im
    return frame


def run(seq):
    pics = list(seq)

    class Shot:
        def __init__(s, img):
            s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')

    class Screen:
        monitors = [{}, {}]
        def __enter__(s): return s
        def __exit__(s, *a): pass
        def grab(s, mon):
            if not pics:
                raise KeyboardInterrupt
            return Shot(pics.pop(0))

    sys.modules['mss'] = types.SimpleNamespace(MSS=lambda: Screen())
    sys.stdin = io.StringIO('')
    from shopreader import session
    time.sleep = lambda s: None                   # no waiting between pretend screenshots
    work = tempfile.mkdtemp(prefix='maplereader_scroll_')
    old = os.getcwd()
    os.chdir(work)
    try:
        session.main(['--quiet', '--channel', '3'])
    except KeyboardInterrupt:
        pass
    finally:
        os.chdir(old)
    f = glob.glob(os.path.join(work, 'scans', 'scan_*.txt'))
    return open(f[0], encoding='utf-8').read().splitlines() if f else []


def main():
    kinds = ['S100'] * 9 + ['S46'] + ['I0', 'I1', 'I2', 'I3', 'I4', 'I5'] + ['S100'] * 4
    frame = build(kinds)
    want = collections.Counter({'Screw': 14, 'Squishy Shoes': 2, "Cat's Eye": 1, 'Emerald Earrings': 1,
                                'Great Brown Helmet': 1, 'Ice Wand': 1})
    closed = Image.open(os.path.join(FX, 'live_ch.png')).convert('RGB').resize(frame(0).size)
    fails = []

    def check(name, lines, expect):
        got = collections.Counter(l.split(' | ')[0] for l in lines)
        ok = got == expect
        print(('ok    ' if ok else 'FAILED'), name, dict(got))
        if not ok:
            fails.append(name)

    # 1. wheel one notch at a time, pausing now and then; then close and reopen the shop and scroll again
    seq = [closed] * 2 + [frame(0)] * 3
    for off in range(1, 15):
        seq += [frame(off)] * (3 if off in (3, 7, 10, 14) else 1)
    seq += [closed] * 2 + [frame(0)] * 3 + [frame(o) for o in range(1, 15)] + [frame(14)] * 3 + [closed] * 2
    check('one notch at a time, then the same shop again (nothing new the 2nd time)', run(seq), want)

    # 2. scrolled in jumps of 3 rows, stopping at every view; then back up to the top
    seq = [closed] * 2 + [frame(0)] * 3
    for off in (3, 6, 9, 12, 14, 11, 8, 5, 2, 0):
        seq += [frame(off)] * 3
    seq += [closed] * 2
    check('jumps of 3 rows, then back up', run(seq), want)

    # 3. a shop of nothing but screws (one stack of 46 among them), one notch at a time
    same = ['S100'] * 9 + ['S46'] + ['S100'] * 6
    frame = build(same)
    seq = [closed] * 2 + [frame(0)] * 3
    for off in range(1, 11):
        seq += [frame(off)] * (3 if off in (4, 8, 10) else 1)
    seq += [closed] * 2
    check('only identical rows, one notch at a time', run(seq), collections.Counter({'Screw': 16}))

    # 4. the same, flicked to the bottom in one go: it can't know how many rows it skipped past, so it
    #    must never count more than are really there (it saw 6 rows for sure)
    seq = [closed] * 2 + [frame(0)] * 3 + [frame(10)] * 3 + [closed] * 2
    got = collections.Counter(l.split(' | ')[0] for l in run(seq))['Screw']
    ok = 6 <= got <= 16
    print(('ok    ' if ok else 'FAILED'), f'flicked straight to the bottom: {got} screws (6 to 16 allowed: it cannot see what it skipped)')
    if not ok:
        fails.append('flick')

    print('SCROLL CHECK PASSED' if not fails else 'SCROLL CHECK FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
