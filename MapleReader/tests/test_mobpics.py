"""Checks the mob pictures: a kill's "before" and "after" screenshots give the one mob that vanished (and nothing
when the camera moved, two mobs vanished, or only a drop or damage number changed); the pictures are kept one per
EXP amount; the EXP recorder pairs the screenshots around a kill by time."""
import os, sys, tempfile, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw                            # noqa: E402
from shopreader import mobpics as MP                        # noqa: E402

fails = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        fails.append(what)


def blob(d, box, seed):
    """A colourful sprite-like thing (random blocks) in `box`."""
    r = random.Random(seed)
    x0, y0, x1, y1 = box
    for y in range(y0, y1, 4):
        for x in range(x0, x1, 4):
            d.rectangle((x, y, x + 3, y + 3), fill=(r.randint(40, 255), r.randint(40, 255), r.randint(0, 120)))


def scene(bg, mob=True, mob2=None, player_seed=1, drop=False, number=False, second_mob=True, shift=0):
    """A game screen: the background, the mob at (300, 500) if `mob`, another mob walking at `mob2`, the player in
    the middle (its animation = `player_seed`), a drop or a damage number at the mob's spot."""
    im = bg.copy()
    d = ImageDraw.Draw(im)
    W, H = im.size
    if mob:
        blob(d, (300, 500, 360, 570), 7)
    if second_mob and mob2 is not None:
        blob(d, (mob2, 600, mob2 + 64, 660), 9)
    blob(d, (W // 2 - 25, 450, W // 2 + 25, 530), player_seed)
    if drop:
        blob(d, (320, 552, 340, 570), 11)
    if number:
        d.text((300, 470), '1234', fill=(255, 80, 80))
    if shift:
        im = im.crop((shift, 0, W, H)).resize((W, H))      # the camera moved
    return im


def catching():
    print('Catching the mob that vanished:')
    bg = Image.open(os.path.join(HERE, 'fixtures', 'live_shop.png')).convert('RGB')
    before = scene(bg, mob=True, mob2=1200, player_seed=1, number=True)
    after = scene(bg, mob=False, mob2=1230, player_seed=2, drop=True)
    after2 = scene(bg, mob=False, mob2=1260, player_seed=3, drop=True)
    box = MP.catch(before, after, after2)
    check(box is not None and abs(box[0] - 300) <= 8 and abs(box[1] - 500) <= 8 and abs(box[2] - 360) <= 8 and abs(box[3] - 570) <= 8,
          f'the dead mob (not the walking one, the player, the drop or the damage number): {box}')
    check(MP.catch(before, scene(bg, mob=False, mob2=1230, player_seed=2, shift=6), after2) is None, 'the camera moved: no picture')
    two_before = before.copy()
    blob(ImageDraw.Draw(two_before), (700, 300, 760, 370), 5)
    check(MP.catch(two_before, after, after2) is None, 'two mobs vanished: no picture (which one was the kill?)')
    after3 = scene(bg, mob=False, mob2=1290, player_seed=4, drop=True)
    check(MP.catch(after, after2, after3) is None, 'nothing died (the other mob only walked on): no picture')
    still = scene(bg, mob=True, mob2=1200, player_seed=1)
    gone = scene(bg, mob=False, mob2=1200, player_seed=1)
    moving = scene(bg, mob=True, mob2=1200, player_seed=1)
    blob(ImageDraw.Draw(moving), (300, 500, 360, 570), 8)   # the mob's spot still changing afterwards
    check(MP.catch(still, gone, moving) is None, 'the spot keeps changing afterwards: not a kill')
    # a dropped item (a 32 px icon) picked up at the moment of the kill, the mob itself beside the player (skipped):
    # the item must not become the mob's picture (seen on the owner's EXP tab: a scroll icon for a 14 EXP mob)
    picked = scene(bg, mob=False, mob2=1200, player_seed=1)
    blob(ImageDraw.Draw(picked), (700, 540, 732, 572), 13)
    check(MP.catch(picked, gone, gone) is None, 'a picked-up drop (32 px) is not a mob: no picture')
    bigger = scene(bg, mob=False, mob2=1200, player_seed=1)
    blob(ImageDraw.Draw(bigger), (700, 530, 744, 572), 13)
    check(MP.catch(bigger, gone, gone) is not None, 'a 44 px thing that vanished still counts as a mob')
    # a map lamp that blinks (48 px, off a second before the kill and on again two seconds after): not a mob
    lamp_on = scene(bg, mob=False, mob2=1200, player_seed=1)
    blob(ImageDraw.Draw(lamp_on), (700, 300, 748, 348), 17)
    check(MP.catch(lamp_on, gone, gone) is not None, '(without the extra pictures the lamp would pass)')
    check(MP.catch(lamp_on, gone, gone, earlier=gone, after3=gone) is None, 'a blinking lamp: off a second before too: no picture')
    check(MP.catch(lamp_on, gone, gone, earlier=lamp_on, after3=lamp_on) is None, 'a blinking lamp: on again 4 s after: no picture')
    earlier = scene(bg, mob=True, mob2=1170, player_seed=4, number=True)
    after3 = scene(bg, mob=False, mob2=1290, player_seed=5, drop=True)
    box = MP.catch(before, after, after2, earlier, after3)
    check(box is not None and abs(box[0] - 300) <= 8, f'the dead mob, there a second earlier and gone 4 s after, still passes: {box}')
    d = tempfile.mkdtemp()
    pics = MP.MobPics(os.path.join(d, 'mobs'), os.path.join(d, 'fight'))
    got = pics.look(22, (before, after, after2))
    check(got is not None and 22 in pics.have and os.path.exists(pics.path(22)), 'the picture is kept as scans/mobs/22.png')
    pic = Image.open(pics.path(22))
    check(50 <= pic.width <= 80 and 60 <= pic.height <= 120, f'the picture is the mob, with a little around it: {pic.size}')
    check(not pics.keep(22, pic) and MP.MobPics(os.path.join(d, 'mobs')).have == {22}, 'the first clear picture wins; the folder is read again at start')
    pics.forget(22)
    check(22 not in pics.have and not os.path.exists(pics.path(22)), 'a wrong picture can be dropped')
    for i in range(MP.FIGHT_KEEP + 2):
        pics.save_fight(22, (before, after, after2, earlier, after3), stamp=f'20261022_{i:06d}')
    files = sorted(os.listdir(os.path.join(d, 'fight')))
    check(len(files) == MP.FIGHT_KEEP * 5 and files[0].startswith('20261022_000002'),
          f'fight pictures: at most {MP.FIGHT_KEEP} kills kept, the oldest dropped ({len(files)} files)')


def pairing():
    print('The EXP recorder pairs the screenshots around a kill:')
    from shopreader.scanner import ExpRunner

    class Tracker:
        last_kills, gain_t = [], None

    class Pics:
        def __init__(self):
            self.got = []

        def look(self, exp, frames):
            self.got.append((exp, frames))

        def save_fight(self, exp, frames):
            self.got.append(('fight', exp))
    tr, pics = Tracker(), Pics()
    r = ExpRunner(tr, mobpics=pics, fight=lambda: True)
    frames = {t: Image.new('RGB', (8, 8), (t, t, t)) for t in range(0, 8)}
    for t in range(0, 8):
        if t == 3:
            tr.last_kills, tr.gain_t = [(22, 1)], 3          # a kill seen at t = 3
        r.saw(frames[t], t)
    check(len(pics.got) == 2 and pics.got[0][0] == 22 and pics.got[0][1] == (frames[1], frames[5], frames[6], frames[0], frames[7]),
          'before = 2 and 3 s before the kill, after = 2, 3 and 4 s after it')
    check(pics.got[1] == ('fight', 22), 'the whole pictures are saved when the fight_pics setting is on')
    tr.last_kills, tr.gain_t, pics.got = [(22, 2)], 10, []
    r.saw(frames[0], 10)
    check(not r.pending, 'two kills in one rise: no picture (which one?)')


if __name__ == '__main__':
    catching()
    pairing()
    print()
    if fails:
        print(f'Mob pictures: {len(fails)} FAILED')
        sys.exit(1)
    print('Mob pictures: all checks passed.')
