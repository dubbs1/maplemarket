"""Reading the shop's name from the white title bar above the list."""
import re
from PIL import Image, ImageOps, ImageChops
from .config import CFG
from . import engine
from .names import fix_w


def title_band(img, lay):
    """Find the shop's white title bar: rows above the list where nearly every pixel is white."""
    h, x = lay['h'], lay['cols'][-1]
    x0, x1 = max(0, int(x - 0.5 * h)), min(img.width, int(x + 8 * h))
    y0, y1 = max(0, int(lay['top'] - 5.8 * h)), max(1, int(lay['top'] - 3.3 * h))
    if y1 - y0 < 8:
        return None
    strip = ImageOps.grayscale(img.crop((x0, y0, x1, y1)))
    W = strip.width
    px = strip.load()
    white = [sum(1 for i in range(0, W, 3) if px[i, j] >= 240) / max(1, len(range(0, W, 3))) for j in range(strip.height)]
    best, run = None, None
    for j, f in enumerate(white + [0]):
        if f > 0.35 and run is None:              # text rows still count: the letters only cover part of the bar
            run = j
        if f <= 0.35 and run is not None:
            if j - run >= 0.25 * h and (best is None or j - run > best[1] - best[0]):
                best = (run, j)
            run = None
    if not best:
        return None
    pad = max(2, int(0.06 * h))
    return (max(0, int(x - 0.74 * h)), max(0, y0 + best[0] - pad), min(img.width, int(x + 9 * h)), y0 + best[1] + pad)


TITLE_CACHE = {}


def read_title(img, lay):
    """Read the shop's name from its title bar: trim to the letters, read it three ways,
    and keep the name at least two readings agree on (short names like "S" or "711" are tricky)."""
    box = title_band(img, lay)
    if not box or box[3] - box[1] < 6:
        return None
    g0 = ImageOps.grayscale(img.crop(box))
    tb = g0.resize((96, 12))
    c = TITLE_CACHE
    where = (box, g0.size)                           # the bar's place and size, before trimming to the letters
    if c.get('thumb') is not None and c.get('where') == where and \
            ImageChops.difference(c['thumb'], tb).point(lambda v: 255 if v > 30 else 0).histogram()[255] < 6:
        return c['name']                             # same title bar as last read (you scrolled): no need to read again
    px = g0.load()
    cols = [i for i in range(g0.width) if any(px[i, j] < 150 for j in range(g0.height))]
    if not cols:
        return None
    g0 = g0.crop((max(0, cols[0] - 6), 0, min(g0.width, cols[-1] + 6), g0.height))
    key = lambda t: re.sub(r'[^a-z0-9<]', '', t.lower())
    reads = []
    for sc, psm in ((2, '6'), (3, '6'), (3, '7')):
        g = ImageOps.autocontrast(g0.resize((g0.width * sc, g0.height * sc), Image.LANCZOS))
        txt = engine.text(ImageOps.expand(g, border=20, fill=255), config='--psm ' + psm + ' ' + CFG)
        line = next((t for t in txt.splitlines() if key(t)), '')
        line = re.sub(r'\s+', ' ', line).strip(' |:;[]_\'"').lstrip('.,“”‘’`~-* ')
        line = re.sub(r'^[^AIai0-9<]\s+', '', line)     # stray mark from the title bar's dotted edge
        line = re.sub(r'^[^A-Za-z0-9<]+', '', line)      # leftover symbols like ¥ in front
        line = re.sub(r'^(?:(?=\S*[=.,:;|~])[^A-Za-z\s]*[A-Za-z]?[^A-Za-z\s]*\s+)+', '', line)   # junk bits in front, e.g. "y= . ROLLS AND MORE"
        line = re.sub(r'\bV(?=hite\b)', 'W', fix_w(line))   # "Ywhite"/"Vhite" -> "White"
        if key(line) and len(line) < 40:
            reads.append(line)
    for i, r in enumerate(reads):
        if sum(key(o) == key(r) for o in reads) >= 2:
            TITLE_CACHE.update(thumb=tb, where=where, name=r)
            return r
    return None
