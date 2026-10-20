"""Reads every picture in tests/fixtures and checks the result against tests/fixtures/expected.

Run with run_tests.bat (or: py -3.13 tests/test_pictures.py). Takes about a minute.

The expected files were made with Tesseract 5.3. Other Tesseract versions can read the odd letter
differently, so a picture passes when it finds the same number of listings and at least 9 in 10 lines
are identical; any differences are printed so you can see them.

It also checks the fast and the standard way of running Tesseract give the same answers.
After an intended change, rebuild the expected files with:  py -3.13 tests/test_pictures.py --update
"""
import contextlib, io, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image                                   # noqa: E402
from shopreader import engine, rows as R                # noqa: E402
from shopreader.ocr import find_tesseract               # noqa: E402
from shopreader.session import read_picture             # noqa: E402

FX = os.path.join(HERE, 'fixtures')
EXP = os.path.join(FX, 'expected')
SAME_ENGINE_PICTURES = ('sold.png', 'wcc.png', 'gear_mats.png')


def picture_output(path):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        read_picture(path, [])
    return buf.getvalue()


def compare(got, want):
    """(passes, number of differing lines, the differing pairs)"""
    g, w = got.splitlines(), want.splitlines()
    pairs = [(a, b) for a, b in zip(g + [''] * len(w), w + [''] * len(g)) if a != b][:max(len(g), len(w))]
    listings = lambda ls: sum(' | ' in x for x in ls)
    ok = listings(g) == listings(w) and len(pairs) <= 0.1 * max(1, len(w))
    return ok, len(pairs), pairs


def check_engines():
    """Fast and standard Tesseract must read pictures the same way."""
    if engine.use('fast') != 'fast':
        print('fast Tesseract did not load: the reader will use the standard way (slower, still works)')
        return 0
    bad = 0
    for name in SAME_ENGINE_PICTURES:
        pic = os.path.join(FX, name)
        t = time.time(); fast = picture_output(pic); tf = time.time() - t
        engine.use('slow')
        t = time.time(); slow = picture_output(pic); ts = time.time() - t
        engine.use('fast')
        same = fast == slow
        bad += not same
        print(f"{'ok     ' if same else 'DIFFERS'} fast vs standard on {name}: {tf:.1f}s vs {ts:.1f}s")
        if not same:
            for a, b in zip(fast.splitlines(), slow.splitlines()):
                if a != b:
                    print('   fast:', a, '\n   std: ', b)
    return bad


def main():
    update = '--update' in sys.argv
    os.chdir(tempfile.mkdtemp(prefix='maplereader_test_'))   # keep check pictures out of your scans folder
    if not find_tesseract():
        print('Tesseract not found.'); return 1
    print('Text reading:', engine.mode())
    bad, quick_same, quick_all = 0, 0, 0
    for name in sorted(os.listdir(EXP)):
        pic = os.path.join(FX, name[:-4])                # "shop2.jpg.txt" -> "shop2.jpg"
        got = picture_output(pic)
        want_path = os.path.join(EXP, name)
        if update:
            open(want_path, 'w', encoding='utf-8').write(got)
            print('updated', name); continue
        want = open(want_path, encoding='utf-8').read()
        ok, n, pairs = compare(got, want)
        bad += not ok
        print(('ok     ' if ok else 'CHANGED'), name[:-4], '' if not n else f'({n} line(s) read differently)')
        for g, w in pairs:
            print('   now:', g, '\n   was:', w)
        # quick read (used after scrolling) must find the same listings and prices as the full read
        im = Image.open(pic).convert('RGB')
        full, _, lay = R.parse_frame(im, [])
        if full and lay and lay.get('fast'):
            R.ROW_CACHE.clear()
            quick, _, _ = R.parse_frame(im, [], dict(lay))
            quick_all += 1
            # same listings and prices (a name may differ by a letter between the two ways of reading)
            quick_same += [(r['each'], bool(r.get('sold'))) for r in full] == \
                          [(r['each'], bool(r.get('sold'))) for r in quick]
    if update:
        return 0
    print(f'\nquick read matched the full read on {quick_same} of {quick_all} pictures')
    if quick_all and quick_same < 0.8 * quick_all:
        bad += 1
        print('QUICK READ: too many differences')
    print()
    bad += check_engines()
    print('ALL PICTURE CHECKS PASSED' if not bad else f'{bad} PICTURE CHECK(S) FAILED')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
