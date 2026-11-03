"""A picture of each mob you kill, cut from the screen (scans/mobs/<EXP>.png, one per EXP amount), so the Mobs page
can show what a "22 EXP each" mob looks like and you can name it in the app. Screenshots only.

How: the EXP recorder keeps the last few screenshots. When a kill is seen (an EXP rise of one amount), the picture
from 2 s before the rise (the mob alive) is compared with the one 2 s after it (the mob gone, its death animation
over), and the pictures 3 s before and 3 and 4 s after confirm it: the mob was there before too, and its spot
stays empty (a blinking map lamp fails that). It is kept only when the kill is clear (`catch`): the camera didn't
move (nearly all of the screen is the same), exactly one mob-sized thing vanished (not the player in the middle of
the screen, not a floating damage number, not a dropped item picked up just then: its icon is 32 px, a mob is
bigger), and its spot stays still afterwards. Otherwise no picture this time: the kill still counts, the next clear
one brings the picture.

The kills confirm each other (`MobPics.offer`): every clear catch for an amount is matched against the ones before
(`alike`: the same size, the same look, either way round); the look caught most often is the picture shown, so a
one-off (a lamp, a drop) caught first gives way once the mob itself is caught twice. "Not this mob" moves the
picture to scans/mobs/not/, and anything alike to it is never kept again.

With the `fight_pics` setting on, the five screenshots around each kill are saved whole in scans/fight (at most
FIGHT_KEEP kills, oldest replaced; the setting is off again when the app next opens): for tuning on a real screen."""
import os
import time
from PIL import Image, ImageChops

CELL = 8                       # the change map's cell size (pixels): blobs are found on this grid
STILL = 0.08                   # more of the screen than this changed: the camera moved (or a lot happened): not clear
GONE_STILL = 0.04              # the mob's spot must change less than this between the two "after" pictures
MIN_PX, MAX_PX = 24, 220       # a mob's width and height on screen (damage numbers and drops are smaller)
MOB_PX = 40                    # the vanished thing's longer side, measured to the pixel: a dropped item's icon is 32 px
PLAYER_BAND = 0.055            # the player stands in the middle: blobs within this (of the width) of it are skipped
FIGHT_KEEP = 30                # kills kept whole by the fight_pics setting
KEEP = 300                     # mob pictures kept
CANDS = 3                      # looks remembered per amount while they confirm each other
ALIKE = 0.5                    # two crops are the same mob when their small grey copies correlate at least this much
NOT_KEEP = 5                   # "not this mob" pictures remembered per amount


def _changed(a, b, tol=40):
    """A black/white picture of where a and b differ (any channel by more than tol)."""
    d = ImageChops.difference(a, b)
    r, g, bl = d.split()[:3]
    return ImageChops.lighter(ImageChops.lighter(r, g), bl).point(lambda v: 255 if v > tol else 0)


def _cells(mask):
    """The change map on the CELL grid: a cell is on when at least a quarter of its pixels changed."""
    small = mask.reduce(CELL)                      # (the mean of each cell)
    return small.point(lambda v: 255 if v >= 64 else 0)


def _blobs(cells):
    """Boxes (in pixels) of the connected on-cells of a change map."""
    w, h = cells.size
    px = cells.load()
    seen = set()
    out = []
    for y in range(h):
        for x in range(w):
            if (x, y) in seen or not px[x, y]:
                continue
            stack, x0, y0, x1, y1 = [(x, y)], x, y, x, y
            seen.add((x, y))
            while stack:
                cx, cy = stack.pop()
                x0, y0, x1, y1 = min(x0, cx), min(y0, cy), max(x1, cx), max(y1, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1), (cx - 1, cy - 1), (cx + 1, cy + 1), (cx - 1, cy + 1), (cx + 1, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and px[nx, ny]:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            out.append((x0 * CELL, y0 * CELL, (x1 + 1) * CELL, (y1 + 1) * CELL))
    return out


def _fraction(mask, box=None):
    m = mask.crop(box) if box else mask
    h = m.histogram()
    return h[255] / max(1, m.width * m.height)


def catch(before, after, after2, earlier=None, after3=None):
    """The box of the one mob that vanished between `before` and `after` (and whose spot is still in `after2`),
    or None when it isn't clear. All the pictures are the same size. With `earlier` (a second before `before`)
    the thing must have been there then too, and with `after3` its spot must still be still a second later:
    a map lamp that blinks (the owner's Kerning subway: a red light switching off at a kill became "the mob")
    fails both, a mob that stood there and died passes both."""
    if not (before.size == after.size == after2.size):
        return None
    chg = _changed(before, after)
    if _fraction(chg) > STILL:
        return None                                # the camera moved, or too much is going on
    W = before.width
    found = []
    for box in _blobs(_cells(chg)):
        bw, bh = box[2] - box[0], box[3] - box[1]
        if not (MIN_PX <= bw <= MAX_PX and MIN_PX <= bh <= MAX_PX):
            continue                               # a damage number, a drop, or something far bigger than a mob
        if abs((box[0] + box[2]) / 2 - W / 2) < PLAYER_BAND * W:
            continue                               # the player (the camera keeps them in the middle)
        exact = chg.crop(box).getbbox()            # the thing itself, not the 8 px cells around it
        if exact is None or max(exact[2] - exact[0], exact[3] - exact[1]) < MOB_PX:
            continue                               # a dropped item picked up at the same moment (an icon is 32 px): not a mob
        tight = (box[0] + exact[0], box[1] + exact[1], box[0] + exact[2], box[1] + exact[3])
        if _fraction(_changed(after, after2), box) > GONE_STILL:
            continue                               # still moving there: a mob that walked, not one that died
        if after3 is not None and _fraction(_changed(after2, after3), box) > GONE_STILL:
            continue                               # something came back (a blinking lamp, a mob walking in)
        if earlier is not None and _fraction(_changed(earlier, after), box) < 0.5 * _fraction(chg, box):
            continue                               # it wasn't there a second before: a blink, not a mob standing there
        found.append(tight)
    return found[0] if len(found) == 1 else None   # two vanished: can't tell which the kill was


def alike(a, b):
    """Are two crops the same mob? About the same size, and their small grey copies (or one mirrored: a mob faces
    either way) match: the correlation of the two, brightness taken out, is at least ALIKE."""
    if not (0.6 <= a.width / b.width <= 1.7 and 0.6 <= a.height / b.height <= 1.7):
        return False
    sa, sb = (im.convert('L').resize((24, 24)) for im in (a, b))
    return max(_corr(sa, sb), _corr(sa, sb.transpose(Image.FLIP_LEFT_RIGHT))) >= ALIKE


def _corr(a, b):
    """The correlation (-1 to 1) of two equal-sized grey pictures."""
    xs, ys = list(a.getdata()), list(b.getdata())
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else 0.0


class MobPics:
    """The pictures kept so far (scans/mobs), the looks still confirming each other, the "not this mob" ones
    (scans/mobs/not), and the fight pictures for tuning (scans/fight)."""
    def __init__(self, folder, fight=None):
        self.folder, self.fight = folder, fight
        self.have = {}                             # exp -> a stamp that changes with the picture (the page reloads it)
        try:
            for f in os.listdir(folder):
                if f.endswith('.png') and f[:-4].isdigit():
                    self.have[int(f[:-4])] = self._stamp(os.path.join(folder, f))
        except OSError:
            pass
        self.cands = {}                            # exp -> [[crop, times caught, is the kept picture], ...]
        self.nots = {}                             # exp -> [crop, ...] from "not this mob" (read when first needed)

    @staticmethod
    def _stamp(path):
        try:
            return os.stat(path).st_mtime_ns // 1_000_000 % 10_000_000
        except OSError:
            return 0

    def path(self, exp):
        return os.path.join(self.folder, f'{int(exp)}.png')

    def _not_dir(self):
        return os.path.join(self.folder, 'not')

    def _write(self, exp, img):
        try:
            os.makedirs(self.folder, exist_ok=True)
            tmp = self.path(exp) + '.tmp'
            img.save(tmp, 'PNG')
            os.replace(tmp, self.path(exp))
        except OSError:
            return False
        self.have[exp] = self._stamp(self.path(exp))
        return True

    def _nots(self, exp):
        """The crops dropped with "not this mob" for this amount."""
        if exp not in self.nots:
            self.nots[exp] = []
            try:
                for f in sorted(os.listdir(self._not_dir())):
                    if f.startswith(f'{int(exp)}_') and f.endswith('.png'):
                        with Image.open(os.path.join(self._not_dir(), f)) as im:
                            self.nots[exp].append(im.convert('RGB').copy())
            except OSError:
                pass
        return self.nots[exp]

    def offer(self, exp, img):
        """A clear catch of the mob giving `exp`: the picture shown is the look caught most often (ties: the one
        kept already). Nothing alike to a "not this mob" picture is kept. True when the kept picture changed."""
        if any(alike(img, n) for n in self._nots(exp)):
            return False
        c = self.cands.setdefault(exp, [])
        if exp in self.have and not any(x[2] for x in c):
            try:                                   # the picture from an earlier run starts as the one to beat
                with Image.open(self.path(exp)) as im:
                    c.insert(0, [im.convert('RGB').copy(), 1, True])
            except OSError:
                self.have.pop(exp, None)
        for x in c:
            if alike(x[0], img):
                x[1] += 1
                break
        else:
            if len(c) >= CANDS:                    # a new look takes the place of the least caught one (not the kept one)
                c.remove(min((x for x in c if not x[2]), key=lambda x: x[1]))
            c.append([img, 1, False])
        best = max(c, key=lambda x: (x[1], x[2]))  # most caught; the kept one when tied
        if best[2]:
            return False
        if exp not in self.have and len(self.have) >= KEEP:
            return False
        if not self._write(exp, best[0]):
            return False
        for x in c:
            x[2] = x is best
        return True

    def keep(self, exp, img):
        """Keep `img` as the picture of the mob giving `exp` unless there is one (the first clear one wins until
        another look is caught more often)."""
        if exp in self.have or len(self.have) >= KEEP:
            return False
        return self.offer(exp, img)

    def forget(self, exp):
        """"Not this mob": the picture goes to scans/mobs/not/ and nothing alike to it is kept again."""
        nots = self._nots(exp)
        try:
            with Image.open(self.path(exp)) as im:
                nots.append(im.convert('RGB').copy())
            del nots[:-NOT_KEEP]
            os.makedirs(self._not_dir(), exist_ok=True)
            for f in sorted(os.listdir(self._not_dir()))[::-1]:
                if f.startswith(f'{int(exp)}_') and f.endswith('.png'):
                    os.remove(os.path.join(self._not_dir(), f))
            for k, im in enumerate(nots):
                im.save(os.path.join(self._not_dir(), f'{int(exp)}_{k}.png'), 'PNG')
            os.remove(self.path(exp))
        except OSError:
            try:
                os.remove(self.path(exp))
            except OSError:
                pass
        self.have.pop(exp, None)
        self.cands.pop(exp, None)

    def look(self, exp, frames):
        """A kill of `exp` EXP was seen: frames = (before, after, after2[, earlier, after3]). Offers the mob's
        picture when it's clear."""
        box = catch(*frames)
        if box is not None:
            pad = 4
            x0, y0, x1, y1 = max(0, box[0] - pad), max(0, box[1] - pad), min(frames[0].width, box[2] + pad), min(frames[0].height, box[3] + pad)
            self.offer(exp, frames[0].crop((x0, y0, x1, y1)))
        return box

    def save_fight(self, exp, frames, stamp=None):
        """The fight_pics setting: the whole pictures around a kill, for tuning (oldest kills replaced)."""
        if not self.fight:
            return
        try:
            os.makedirs(self.fight, exist_ok=True)
            stamp = stamp or time.strftime('%Y%m%d_%H%M%S')
            for name, img in zip(('before', 'after', 'after2', 'earlier', 'after3'), frames):
                if img is not None:
                    img.save(os.path.join(self.fight, f'{stamp}_{int(exp)}_{name}.png'), 'PNG')
            old = sorted(f for f in os.listdir(self.fight) if f.endswith('.png'))
            for f in old[:-FIGHT_KEEP * len(frames)]:
                os.remove(os.path.join(self.fight, f))
        except OSError:
            pass
