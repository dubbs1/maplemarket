"""A picture of each mob you kill, cut from the screen (scans/mobs/<EXP>.png, one per EXP amount), so the EXP tab
can show what a "22 EXP each" mob looks like and you can name it in the app. Screenshots only.

How: the EXP recorder keeps the last few screenshots. When a kill is seen (an EXP rise of one amount), the picture
from 2 s before the rise (the mob alive) is compared with the one 2 s after it (the mob gone, its death animation
over), and the pictures 3 s before and 3 and 4 s after confirm it: the mob was there before too, and its spot
stays empty (a blinking map lamp fails that). It is kept only when the kill is clear (`catch`): the camera didn't move (nearly all of the screen is the
same), exactly one mob-sized thing vanished (not the player in the middle of the screen, not a floating damage
number, not a dropped item picked up just then: its icon is 32 px, a mob is bigger), and its spot stays still
afterwards. Otherwise no picture this time: the kill still counts,
the next clear one brings the picture.

With the `fight_pics` setting on, the four screenshots around each kill are saved whole in scans/fight (at most
FIGHT_KEEP kills, oldest replaced; the setting is off again when the app next opens): for tuning on a real screen."""
import os
import time
from PIL import ImageChops

CELL = 8                       # the change map's cell size (pixels): blobs are found on this grid
STILL = 0.08                   # more of the screen than this changed: the camera moved (or a lot happened): not clear
GONE_STILL = 0.04              # the mob's spot must change less than this between the two "after" pictures
MIN_PX, MAX_PX = 24, 220       # a mob's width and height on screen (damage numbers and drops are smaller)
MOB_PX = 40                    # the vanished thing's longer side, measured to the pixel: a dropped item's icon is 32 px
PLAYER_BAND = 0.055            # the player stands in the middle: blobs within this (of the width) of it are skipped
FIGHT_KEEP = 30                # kills kept whole by the fight_pics setting
KEEP = 300                     # mob pictures kept


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
        if _fraction(_changed(after, after2), box) > GONE_STILL:
            continue                               # still moving there: a mob that walked, not one that died
        if after3 is not None and _fraction(_changed(after2, after3), box) > GONE_STILL:
            continue                               # something came back (a blinking lamp, a mob walking in)
        if earlier is not None and _fraction(_changed(earlier, after), box) < 0.5 * _fraction(chg, box):
            continue                               # it wasn't there a second before: a blink, not a mob standing there
        found.append(box)
    return found[0] if len(found) == 1 else None   # two vanished: can't tell which the kill was


class MobPics:
    """The pictures kept so far (scans/mobs), and the fight pictures for tuning (scans/fight)."""
    def __init__(self, folder, fight=None):
        self.folder, self.fight = folder, fight
        try:
            self.have = {int(f[:-4]) for f in os.listdir(folder) if f.endswith('.png') and f[:-4].isdigit()}
        except OSError:
            self.have = set()

    def path(self, exp):
        return os.path.join(self.folder, f'{int(exp)}.png')

    def keep(self, exp, img):
        """Keep `img` as the picture of the mob giving `exp` (the first clear one wins)."""
        if exp in self.have or len(self.have) >= KEEP:
            return False
        try:
            os.makedirs(self.folder, exist_ok=True)
            tmp = self.path(exp) + '.tmp'
            img.save(tmp, 'PNG')
            os.replace(tmp, self.path(exp))
        except OSError:
            return False
        self.have.add(exp)
        return True

    def forget(self, exp):
        try:
            os.remove(self.path(exp))
        except OSError:
            pass
        self.have.discard(exp)

    def look(self, exp, frames):
        """A kill of `exp` EXP was seen: frames = (before, after, after2[, earlier, after3]). Keeps the mob's
        picture when it's clear."""
        box = catch(*frames)
        if box is not None:
            pad = 4
            x0, y0, x1, y1 = max(0, box[0] - pad), max(0, box[1] - pad), min(frames[0].width, box[2] + pad), min(frames[0].height, box[3] + pad)
            self.keep(exp, frames[0].crop((x0, y0, x1, y1)))
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
