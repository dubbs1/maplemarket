"""Your mesos, read from the Item window's meso box (a gold coin, then a white box with the amount, then "MESOS").
Only while the Item window is open; the EXP log's mesos per hour is how much the amount grows during a run.
Screenshots only, like everything else."""
import re
from PIL import Image, ImageChops, ImageOps
from . import engine

_COIN = lambda p: p[0] > 190 and 120 < p[1] < 235 and p[2] < 90 and p[0] - p[2] > 120   # the gold coin


def find_box(img):
    """The white meso box, (x0, y0, x1, y1), or None: a long band of white rows, 12-30 px tall, with the gold coin
    just left of it. Colour only (~30 ms on a 1080p screen)."""
    r, g, b = img.split()[:3]
    white = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v > 240 else 0), g.point(lambda v: 255 if v > 240 else 0)),
                                b.point(lambda v: 255 if v > 236 else 0))
    bands, live = [], []                             # stretches of white at least 90 px long, joined row to row
    for y in range(img.height):
        row = white.crop((0, y, img.width, y + 1)).tobytes()
        nxt = []
        for m in re.finditer(rb'\xff{90,}', row):
            for band in live:
                if abs(band[2] - m.start()) <= 2:       # (rows through the digits end where the digits start)
                    band[1], band[3] = y, max(band[3], m.end())
                    nxt.append(band)
                    break
            else:
                band = [y, y, m.start(), m.end()]
                bands.append(band)
                nxt.append(band)
        live = nxt
    px = img.load()
    for y0, y1, x0, x1 in bands:
        h = y1 - y0 + 1
        if not 10 <= h <= 32 or x1 - x0 > 25 * h:
            continue
        gold = lambda ya, yb: sum(_COIN(px[x, y]) for x in range(max(0, int(x0 - 1.4 * h)), x0) for y in range(max(0, ya), min(img.height, yb)))
        coin = gold(y0, y1 + 1)
        if coin >= 0.2 * h * h and gold(y0 - h // 2, y0) + gold(y1 + 1, y1 + 1 + h // 2) < coin * 0.2:
            return (x0, y0, x1, y1 + 1)              # a round gold coin just left of the box (not a gold frame running past)
    return None


def read_mesos(img, box=None):
    """The meso amount in the Item window (an int), or None when the window isn't open or the amount can't be read."""
    box = box or find_box(img)
    if not box:
        return None
    x0, y0, x1, y1 = box
    crop = img.crop((x0 + 2, y0 + 1, x1 - 2, y1 - 1)).convert('L')
    votes = {}
    for sc in (2, 3, 4):
        g = ImageOps.autocontrast(crop).resize((crop.width * sc, crop.height * sc), Image.LANCZOS)
        t = engine.text(ImageOps.expand(g, border=10, fill=255), config='--psm 7 -c tessedit_char_whitelist=0123456789,')
        t = t.strip().replace(' ', '')
        if re.fullmatch(r'\d{1,3}(,\d{3})*', t):    # commas in the right places: a clean read
            votes[int(t.replace(',', ''))] = votes.get(int(t.replace(',', '')), 0) + 1
    if not votes:
        return None
    best = max(votes, key=votes.get)
    return best if votes[best] >= 2 else None        # two reads must agree
