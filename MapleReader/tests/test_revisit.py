"""Checks seeing the same shops again: nothing saved twice, and what changed is recorded.

1. Stop and Start (or close and reopen the app) in the middle of the Free Market: the same pretend session played
   twice in the same folder saves its 29 listings once, and chimes once per shop.
2. A shop's whole list seen again: a listing that's gone (bought, taken back, re-priced) gets a "gone" line, one
   that turned sold doesn't; a listing seen only partly (not scrolled to the end) never makes "gone" lines;
   one that comes back is saved again.
3. Knowing when the whole list was seen: a 5-listing shop (no scrollbar handle, empty slot below) is whole;
   a 6-listing view with a handle, not scrolled, isn't.
4. A screenshot that fails (PC locked) doesn't stop watching.
"""
import os, sys, tempfile, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from PIL import Image                                       # noqa: E402

FX = os.path.join(HERE, 'fixtures')
fails = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        fails.append(what)


def lines():
    with open(os.path.join('scans', 'all_scans.txt'), encoding='utf-8') as f:
        return [ln for ln in f.read().splitlines() if ln.strip()]


def session_twice():
    print('Stop and Start in the middle of the market:')
    import test_session as TS
    from shopreader import scanner

    class Shot:
        def __init__(s, img):
            s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')

    def run():
        pics = TS.frames()

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
        beeps = []
        scanner.beep = lambda v: beeps.append(v)

        class Ev(scanner.Events):
            def message(self, text): pass
            def saved(self, rows, room, ch, total): pass
            def gone(self, rows, room, ch): pass
        sc = scanner.Scanner(events=Ev(), interval=0)
        sc.run()
        return sc.saver.total, len(beeps)

    scanner.time = types.SimpleNamespace(sleep=lambda s: None, time=__import__('time').time)
    first = run()
    n = len(lines())
    second = run()
    check(first[0] == TS.EXPECTED_LINES, f'first time: {first[0]} listings saved, {first[1]} chimes')
    check(second == (0, 0), f'watching again: {second[0]} saved again, {second[1]} chimes')
    check(len(lines()) == n, f'all_scans.txt unchanged by the second look ({n} lines)')


def gone():
    print('A shop seen whole again:')
    from shopreader import scanner
    got = []

    class Ev(scanner.Events):
        def message(self, text): pass
        def saved(self, rows, room, ch, total): pass
        def gone(self, rows, room, ch): got.extend(rows)
    scanner.beep = lambda v: None
    st = {'ch': 5, 'room': 3}
    sv = scanner.Saver('mine.txt', st, Ev())
    row = lambda item, each, copy=1, sold=False: dict(item=item, each=each, shop='Revisit Shop', copy=copy, sold=sold)
    sv.save([row('Ilbi', 100), row('Ilbi', 100, 2), row('Blue Lutia', 200), row('Ore', 300)], 3, whole=True)
    check(not got, 'the first whole look has nothing to compare with')
    sv.save([row('Ilbi', 100), row('Ilbi', 100, sold=True), row('Blue Lutia', 150)], 3, whole=False)
    check(not got, 'a part of the list (not scrolled to the end) makes no "gone" lines')
    sv.save([row('Ilbi', 100), row('Ilbi', 100, sold=True), row('Blue Lutia', 150)], 3, whole=True)
    names = sorted((g['item'], g['each'], g['copy']) for g in got)
    check(names == [('Blue Lutia', 200, 1), ('Ore', 300, 1)], f'gone: re-priced and taken-off listings {names}')
    gl = [ln for ln in lines() if '| gone' in ln]
    check(len(gl) == 2 and all('Revisit Shop | 3 | 5 | gone | c1 | @' in ln for ln in gl), f'written as gone lines {gl[:1]}')
    n = len(lines())
    sv2 = scanner.Saver('mine.txt', st, Ev())          # the app opened again: it remembers the shop
    sv2.save([row('Ilbi', 100), row('Ilbi', 100, sold=True), row('Blue Lutia', 150), row('Ore', 300)], 3, whole=True)
    back = [ln for ln in lines()[n:]]
    check(len(back) == 1 and back[0].startswith('Ore | 300 |') and '| gone' not in back[0],
          f'a gone listing that comes back is saved again (after a restart too): {back}')


def whole():
    print('Knowing the whole list was seen:')
    from shopreader import ocr
    from shopreader.rows import parse_frame
    from shopreader.scroll import ScrollTracker
    ocr.find_tesseract()
    for name, want in (('shopS.png', True), ('live_shop.png', False)):
        img = Image.open(os.path.join(FX, name)).convert('RGB')
        rows, _, lay = parse_frame(img, [], None)
        t = ScrollTracker()
        t.place(img, lay, rows)
        check(t.whole == want, f'{name}: {len(rows)} listings, whole list {t.whole}')
    # a listing whose text wasn't read must not look like the end of the list
    img = Image.open(os.path.join(FX, 'shopS.png')).convert('RGB')
    rows, _, lay = parse_frame(img, [], None)
    t = ScrollTracker()
    t.place(img, lay, rows[:4])
    check(not t.whole, 'shopS.png with its 5th listing unread: not whole (that slot is not empty)')


def room_typed():
    print('The minimap can\'t be read: shops wait a little for the room, typed by hand:')
    import test_session as TS
    from shopreader import scanner
    from PIL import ImageDraw

    def run(type_at, wait):
        pics = []
        for im in TS.frames():
            im = im.copy()
            ImageDraw.Draw(im).rectangle((0, 0, im.width // 4, im.height // 4), fill=(0, 0, 0))   # no minimap
            pics.append(im)
        n = [0]

        class Shot:
            def __init__(s, img):
                s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')

        class Screen:
            monitors = [{}, {}]
            def grab(s, mon):
                n[0] += 1
                if n[0] == type_at:
                    sc.set_room(2)                   # typed on the Scan tab, part-way through
                if not pics:
                    sc.stop()
                    return Shot(Image.new('RGB', (64, 64)))
                return Shot(pics.pop(0))
        sys.modules['mss'] = types.SimpleNamespace(MSS=Screen)
        scanner.ROOM_WAIT = wait
        scanner.beep = lambda v: None

        class Ev(scanner.Events):
            def message(self, text): pass
            def saved(self, rows, room, ch, total): pass
        os.makedirs('roomtest', exist_ok=True)
        old = os.getcwd()
        os.chdir(tempfile.mkdtemp(dir='roomtest'))
        try:
            sc = scanner.Scanner(events=Ev(), interval=0)
            sc.run()
            return sorted({ln.split(' | ')[3] for ln in lines()}), sc.saver.total
        finally:
            os.chdir(old)
    scanner.time = types.SimpleNamespace(sleep=lambda s: None, time=__import__('time').time)
    rooms, total = run(type_at=12, wait=60)
    check(rooms == ['2'] and total == 29, f'typed part-way: every listing saved in room 2 ({rooms}, {total} saved), none as "?"')
    rooms, total = run(type_at=10 ** 6, wait=0.2)
    check(rooms == ['0'] and total > 0, f'never typed: after a short wait they are saved anyway, room unknown ({rooms}, {total} saved)')
    scanner.ROOM_WAIT = 20


def room_windowed():
    print('Your minimap (the game in a window, October 21): read by its title when the usual boxes can\'t:')
    from shopreader import location as L
    from shopreader.ocr import find_tesseract
    find_tesseract()
    corner = Image.open(os.path.join(FX, 'room_windowed.png')).convert('RGB')   # the app's room_check.png, in room 2
    screen = Image.open(os.path.join(FX, 'desk_live.png')).convert('RGB')
    screen.paste(corner, (0, 0))
    for name, img in (('room_check.png', corner), ('in a 2560x1440 screen', screen)):
        w = L.RoomWatcher(keep_picture=False)
        check(w.update(img, [], force=True) == 2 and w.by_title, f'{name}: room {w.room} (by the title: {w.by_title})')
    check(w.update(screen, []) == 2, 'and it keeps reading it that way')


def screen_fails():
    print('The screen can\'t be read for a moment (PC locked, a Windows Yes/No prompt):')
    import test_session as TS
    from shopreader import scanner
    pics, made = TS.frames()[-8:], []

    class Shot:
        def __init__(s, img):
            s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')

    class Screen:
        monitors = [{}, {}]
        def __init__(s): made.append(s); s.n = 0
        def grab(s, mon):
            s.n += 1
            if len(made) == 1:
                raise RuntimeError('BitBlt failed')     # the first screen reader never works (as when locked)
            if not pics:
                sc.stop()
                return Shot(Image.new('RGB', (64, 64)))
            return Shot(pics.pop(0))
    sys.modules['mss'] = types.SimpleNamespace(MSS=Screen)
    scanner.time = types.SimpleNamespace(sleep=lambda s: None, time=__import__('time').time)

    class Ev(scanner.Events):
        def message(self, text): pass
        def saved(self, rows, room, ch, total): pass
    sc = scanner.Scanner(events=Ev(), interval=0)
    sc.run()
    check(len(made) >= 2 and not pics, f'watching carried on: {len(made)} screen readers opened, every picture looked at')


if __name__ == '__main__':
    work = tempfile.mkdtemp(prefix='maplereader_revisit_')
    os.chdir(work)
    os.makedirs('scans')
    session_twice()
    gone()
    whole()
    room_typed()
    room_windowed()
    screen_fails()
    print()
    print('REVISIT CHECK PASSED' if not fails else f'REVISIT CHECK: {len(fails)} FAILED')
    sys.exit(1 if fails else 0)
