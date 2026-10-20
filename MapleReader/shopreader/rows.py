"""Reading the listings: normal rows, faded (sold) rows, the quick re-read after scrolling, and the saved line format."""
import hashlib
import os
from PIL import Image, ImageOps
from .config import CFG, PRICE, ROW_FADED
from .layout import find_layout, fit_layout, read_list
from .names import fix_name, real_name
from .ocr import to_number
from .title import read_title
from . import engine


def _reread_price(img, name, width, row_h, red_first=False):
    """Second, closer look at the price line under a name whose price was misread."""
    box = (max(0, name['x0'] - 4), name['y1'] + 1, min(img.width, name['x0'] + width), min(img.height, name['y1'] + int(0.6 * row_h)))
    if box[3] - box[1] < 6:
        return None
    for red in ((True, False) if red_first else (False, True)):
        c = img.crop(box)
        c = c.resize((c.width * 3, c.height * 3), Image.LANCZOS)
        g = ImageOps.expand(ImageOps.autocontrast(c.split()[0] if red else ImageOps.grayscale(c)), border=10, fill=255)
        t = engine.text(g, config='--psm 7 ' + CFG).strip()
        if PRICE.match(t):
            return t
    return None


# --- one row: the pieces every way of reading a row shares ---

def row_box(img, x, y, h, reach):
    """The picture area of one list row: name line above y, price line below it."""
    return (max(0, x - 6), max(0, int(y - 0.56 * h)), min(img.width, int(x + reach)), min(img.height, int(y + 0.42 * h)))


def _brightness(crop):
    """Darkest and brightest grey inside the row (edges left out)."""
    return ImageOps.grayscale(crop.crop((4, 4, max(5, crop.width - 4), max(5, crop.height - 4)))).getextrema()


def _faded_background(crop):
    """True when most of the row is the near-white of a sold row."""
    small = crop.resize((max(1, crop.width // 4), max(1, crop.height // 4)))
    px = list((getattr(small, 'get_flattened_data', None) or small.getdata)())
    return sum(1 for p in px if all(abs(p[i] - ROW_FADED[i]) <= 8 for i in range(3))) >= 0.3 * len(px)


def _row_text(crop, lo, hi, faded):
    """Read the row's text. Faded rows get a hard black/white split, normal rows extra contrast."""
    g = ImageOps.grayscale(crop)
    if faded:
        thr = (lo + hi) // 2 + 8                     # faint grey text: split it cleanly from the background
        g = g.resize((g.width * 3, g.height * 3), Image.LANCZOS).point(lambda v, t=thr: 0 if v < t else 255)
    else:
        g = ImageOps.autocontrast(g.resize((g.width * 3, g.height * 3), Image.LANCZOS))
    txt = engine.text(ImageOps.expand(g, border=10, fill=255), config='--psm 6 ' + CFG)
    return [t.strip(' |') for t in txt.splitlines() if t.strip()]


def listing(name_text, price_text, items):
    """Turn a name line and a "N for X mesos" line into (item, price each), or None if it's junk."""
    n, cost = PRICE.match(price_text).groups()
    n, cost = max(1, to_number(n)), to_number(cost)
    if cost <= 0:
        return None
    nm = fix_name(name_text.strip(' |').rstrip('.… '), items)
    if not real_name(nm):                            # junk like "ere EE"; keeps short names like "Cat's Eye"
        return None
    return nm, round(cost / n)


def _listing_in(lines, items):
    """Find the price line and the name line just above it."""
    pi = next((i for i, t in enumerate(lines) if PRICE.match(t)), None)
    if not pi:
        return None
    return listing(lines[pi - 1], lines[pi], items)


def faded_rows(img, lay, rows, items):
    """Sold items stay in the list as faded, light-grey rows that normal reading skips.
    Check every row slot that has no listing and read faint text there with boosted contrast."""
    h, out = lay['h'], []
    for x in lay['cols']:
        ys = sorted(r['y'] for r in rows if abs(r['x'] - x) < 0.45 * h)
        if not ys:
            continue
        first, last = ys[0], ys[-1]
        slots = [first + k * h for k in range(-6, int(round((last - first) / h)) + 7)]   # the list shows 6 rows
        for y in slots:
            if any(abs(y - v) < 0.35 * h for v in ys) or y - 0.6 * h < 0 or y + 0.45 * h > img.height:
                continue
            crop = img.crop(row_box(img, x, y, h, 3.9 * h))     # wide enough for long names, short of the scrollbar
            if not _faded_background(crop):
                continue                             # not a faded row's background (outside the list, or a normal row)
            lo, hi = _brightness(crop)
            if lo < 120 or hi - lo < 20:            # dark text = a normal row (already read); no contrast = empty slot
                continue
            got = _listing_in(_row_text(crop, lo, hi, True), items)
            if got:
                out.append(dict(item=got[0], each=got[1], x=x, y=int(y), sold=True))
    return out


ROW_CACHE = {}


def read_row(img, x, y, h, width, items):
    """Read one list row (name line + price line) on its own. Returns a row dict, 'empty', or None if unreadable."""
    box = row_box(img, x, y, h, max(3.9 * h, width + 0.6 * h))
    crop = img.crop(box)
    lo, hi = _brightness(crop)
    if hi - lo < 20:
        return 'empty', box
    faded = lo >= 120 and _faded_background(crop)
    ls = _row_text(crop, lo, hi, faded)
    if sum(ch.isalnum() for t in ls for ch in t) < 3:
        return 'empty', box                          # an empty slot at the bottom of the list
    got = _listing_in(ls, items)
    if not got:
        return None, box
    return dict(item=got[0], each=got[1], x=x, y=int(y), sold=faded), box


def fast_rows(img, lay, items):
    """After you scroll, most rows were already read. Look at the 6 row slots; any row whose pixels
    match one read before is reused, and only new rows are read. Returns None if anything looks off."""
    h, rows = lay['h'], []
    for x in lay['cols']:
        for k in range(6):
            y = lay['top'] + k * h
            if y + 0.42 * h > img.height:
                break
            box = row_box(img, x, y, h, max(3.9 * h, lay['width'] + 0.6 * h))
            key = hashlib.md5(ImageOps.grayscale(img.crop(box)).tobytes()).digest()
            if key in ROW_CACHE:
                r = ROW_CACHE[key]
            else:
                r, _ = read_row(img, x, y, h, lay['width'], items)
                if r is None:
                    return None                          # unclear row (cursor, popup, half-scrolled): do a full read
                ROW_CACHE[key] = r
                if len(ROW_CACHE) > 3000:
                    ROW_CACHE.clear()
            if r != 'empty':
                rows.append(dict(r, x=x, y=int(y)))
    return rows or None


def parse_frame(img, items=(), region=None, allow_find=True):
    """Return (rows, None, layout). rows = list of dict(item, each, shop).
    Pass the layout from the last shop to skip the slow whole-screen search."""
    L, lay = [], None
    if region and region.get('fast'):
        quick = fast_rows(img, region, items)        # scrolled the same list: reuse rows already read
        if quick:
            shop = read_title(img, region) or 'Shop'
            for r in quick:
                r['shop'] = shop
            return quick, None, region
    if region:
        L = read_list(img, region)
        lay = fit_layout(L, region)
        if lay and (lay['top'] < region['top'] - 0.3 * lay['h'] or lay['bottom'] > region['bottom'] + 0.3 * lay['h']):
            L = read_list(img, lay)                  # list grew: read the larger area once more
    if not lay and allow_find:
        lay, L = find_layout(img)                    # colour finder: where the list is
        if lay:
            L = read_list(img, lay)                  # then a clean read of just the text column (no icons)
            lay = fit_layout(L, lay) or lay
    if not lay:
        return [], None, None
    rows = []
    pr = [l for l in L if PRICE.match(l['text'])]
    h = lay['h']
    near = lambda a, b: abs(a['x0'] - b['x0']) < 0.45 * h
    isname = lambda l: not PRICE.match(l['text']) and 'mesos' not in l['text'].lower() and sum(c.isalpha() for c in l['text']) >= 3
    pairs = []
    for p in pr:
        cand = [l for l in L if l is not p and isname(l) and 0 < p['y0'] - l['y1'] < 0.65 * h and near(l, p)]
        if cand:
            nm = max(cand, key=lambda l: l['y1'])
            t = (_reread_price(img, nm, max(150, p['x1'] - p['x0'] + 40), h, red_first=True) if p.get('red') else None) or p['text']
            pairs.append((nm, t, p['x0'], p['y0']))
    used = {id(n) for n, *_ in pairs}
    width = lay['width'] + 40
    for l in L:                                   # names whose price line was misread: look again, closer
        if id(l) in used or not isname(l) or not any(near(l, p) for p in pr):
            continue
        if any(0 < p['y0'] - l['y1'] < 0.65 * h and near(l, p) for p in pr):
            continue
        t = _reread_price(img, l, width, h)
        if t:
            pairs.append((l, t, l['x0'], l['y1'] + int(0.22 * h)))
    for name, ptext, x, y in sorted(pairs, key=lambda q: (q[2] // 50, q[3])):
        got = listing(name['text'], ptext, items)
        if got:
            rows.append(dict(item=got[0], each=got[1], x=x, y=y))
    rows += faded_rows(img, lay, rows, items)
    rows.sort(key=lambda r: (r['x'] // 50, r['y']))
    if rows:                                         # the first row may be a sold one: the title sits above it
        lay['top'] = min(lay['top'], min(r['y'] for r in rows))
        lay['bottom'] = max(lay['bottom'], max(r['y'] for r in rows) + lay['h'] // 3)
    shop = read_title(img, lay) if rows else None
    if rows and not shop:
        shop = 'Shop'
        if not os.path.exists(os.path.join('scans', 'title_check.png')) and os.path.isdir('scans'):
            h, x = lay['h'], lay['cols'][-1]          # keep one picture of what the title area looked like, for fixing
            img.crop((max(0, int(x - 2 * h)), max(0, int(lay['top'] - 6 * h)), min(img.width, int(x + 10 * h)),
                      min(img.height, int(lay['bottom'] + h)))).save(os.path.join('scans', 'title_check.png'))
    for r in rows:
        r['shop'] = shop
    if rows:
        lay['fast'] = len(lay['cols']) == 1 and abs(rows[0]['y'] - lay['top']) < 0.3 * lay['h']
    return rows, None, lay if rows else None


def fmt(r, room, ch, when=None):
    """One saved line: item | each | shop | room | channel [| sold] [| c2] [| @time seen].
    c2 = the 2nd identical listing in that shop, so friends scanning the same shop count it once."""
    line = f"{r['item'].replace('|', ' ')} | {r['each']} | {r['shop'].replace('|', ' ')} | {room} | {ch}"
    if r.get('sold'):
        line += ' | sold'
    if r.get('copy'):
        line += f" | c{r['copy']}"
    if when:
        line += ' | @' + when.strftime('%Y-%m-%dT%H:%M:%S')
    return line
