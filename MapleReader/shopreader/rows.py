"""Reading the listings: normal rows, faded (sold) rows, the quick re-read after scrolling, and the saved line format."""
import hashlib
import os
import re
from PIL import Image, ImageOps
from .config import CFG, FADED_ROWS_WIDE, LIST_ROWS_WIDE, PRICE, REF_ROW, ROW_FADED, ROW_OK
from .layout import blue_lists, find_layout, fit_layout, list_boxes, read_list
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
    if any(',' in x and not re.fullmatch(r'\d{1,3}(,\d{3})+', x) for x in (n, cost)):
        return None                                  # "12,99": a digit was lost; better no price than 1,299
    n, cost = max(1, to_number(n)), to_number(cost)
    if cost <= 0:
        return None
    nm = fix_name(name_text.strip(' |').rstrip('.… '), items)
    if not real_name(nm):                            # junk like "ere EE"; keeps short names like "Cat's Eye"
        return None
    return nm, max(1, (cost + n // 2) // n)          # mesos each, rounded half up; never 0 (1000 for 500)


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


# --- other interface sizes: read the shop area at the size the reading is tuned for ---

def _view_for(img, box, h):
    """The part of the screen around a list: its item pictures on the left, the scrollbar on the right, the title above."""
    return (max(0, int(box[0] - 3 * h)), max(0, int(box[1] - 7 * h)), min(img.width, int(box[2] + 6 * h)),
            min(img.height, int(box[3] + 2.5 * h)))


def _plan(img, region):
    """(zoom, part of the screen, guessed row height) to read; zoom 1 = the screenshot as it is. The row height comes
    from the layout already found, else from the shop list's width (about 4.2 rows wide), so no text is read for it."""
    if region:
        z, h = region.get('zoom', 1), region['h']
        if z == 1:
            return 1, None, h
        box = (min(region['cols']), region['top'], max(region['cols']) + region['width'], region['bottom'])
    else:
        boxes = list_boxes(img)
        if not boxes:
            return 1, None, None
        wide = LIST_ROWS_WIDE if blue_lists(img) else FADED_ROWS_WIDE
        h = (boxes[0][2] - boxes[0][0]) / wide
        if ROW_OK[0] <= h <= ROW_OK[1]:
            return 1, _view_for(img, (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                                      max(b[3] for b in boxes)), h), h
        z = REF_ROW / h
        box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return z, _view_for(img, box, h), h


def _moved(lay, view, z, to_screen):
    """A layout in screen pixels <-> the same layout in the enlarged/shrunk view."""
    if not lay:
        return lay
    if to_screen:
        fx, fy, s = (lambda v: v / z + view[0]), (lambda v: v / z + view[1]), (lambda v: v / z)
    else:
        fx, fy, s = (lambda v: (v - view[0]) * z), (lambda v: (v - view[1]) * z), (lambda v: v * z)
    out = dict(lay, cols=[int(round(fx(c))) for c in lay['cols']], top=int(round(fy(lay['top']))),
               bottom=int(round(fy(lay['bottom']))), h=int(round(s(lay['h']))), width=int(round(s(lay['width']))))
    if to_screen:
        out['zoom'] = z
    return out


def parse_frame(img, items=(), region=None, allow_find=True):
    """Return (rows, None, layout) like _parse_frame, in screen pixels, whatever size the game draws its interface:
    rows outside the comfortable size are read from the shop area enlarged or shrunk to the usual size."""
    z, view, guess = _plan(img, region)
    rows, x, lay = _read_at(img, items, region, allow_find, z, None if z == 1 else view)
    if not lay and not region and z == 1 and guess and view and abs(guess / REF_ROW - 1) > 0.1:
        # nothing found at the size it's drawn, and the rows look bigger or smaller than usual (blurry text from
        # the game's "UI Size" filter reads worse there): look again at the usual size
        return _read_at(img, items, None, allow_find, REF_ROW / guess, view)
    if lay and not region:
        # a newly found list: its rows' real height is known now. If the guess from the list's width was off
        # (rows read at an uncomfortable size), read once more at the size that real height asks for.
        h = lay['h']
        if not ROW_OK[0] <= h * z <= ROW_OK[1]:
            z2 = 1 if ROW_OK[0] <= h <= ROW_OK[1] else REF_ROW / h
            if abs(z2 - z) > 0.03:
                box = (min(lay['cols']), lay['top'], max(lay['cols']) + lay['width'], lay['bottom'])
                again = _read_at(img, items, None, allow_find, z2, None if z2 == 1 else _view_for(img, box, h))
                if len(again[0]) >= len(rows):
                    return again
    return rows, x, lay


def _read_at(img, items, region, allow_find, z, view):
    if z == 1:
        rows, x, lay = _parse_frame(img, items, region and dict(region, zoom=1), allow_find)
        if lay:
            lay['zoom'] = 1
        return rows, x, lay
    part = img.crop(view)
    part = part.resize((max(1, round(part.width * z)), max(1, round(part.height * z))), Image.LANCZOS)
    rows, x, lay = _parse_frame(part, items, _moved(region, view, z, False) if region else None, allow_find)
    for r in rows:
        r['x'], r['y'] = int(round(r['x'] / z + view[0])), int(round(r['y'] / z + view[1]))
    return rows, x, _moved(lay, view, z, True)


def _parse_frame(img, items=(), region=None, allow_find=True):
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
        if lay and region.get('faded'):
            lay['faded'] = True
        if lay and (lay['top'] < region['top'] - 0.3 * lay['h'] or lay['bottom'] > region['bottom'] + 0.3 * lay['h']):
            L = read_list(img, lay)                  # list grew: read the larger area once more
    if not lay and allow_find:
        lay, L = find_layout(img)                    # colour finder: where the list is
        if lay:
            L = read_list(img, lay)                  # then a clean read of just the text column (no icons)
            lay = dict(fit_layout(L, lay) or lay, **({'faded': True} if lay.get('faded') else {}))
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
    if lay.get('faded'):
        # the list was found by its sold rows only: read each row once more on its own, the way sold rows are
        # read (closer and more reliable than the whole column at once); that also says whether it's sold
        for r in rows:
            one, _ = read_row(img, r['x'], r['y'], h, lay['width'], items)
            if isinstance(one, dict):
                r.update(item=one['item'], each=one['each'], sold=one['sold'])
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
    """One saved line: item | each | shop | room | channel [| sold] [| gone] [| c2] [| @time seen].
    c2 = the 2nd identical listing in that shop, so a shop seen twice counts it once.
    The time carries this PC's UTC offset (@2026-10-19T15:31:08-04:00), so a friend in another time
    zone sees the right "just listed" and ages."""
    line = f"{r['item'].replace('|', ' ')} | {r['each']} | {r['shop'].replace('|', ' ')} | {room} | {ch}"
    if r.get('sold'):
        line += ' | sold'
    if r.get('gone'):
        line += ' | gone'                       # no longer in the shop's list (see scanner.Saver)
    if r.get('copy'):
        line += f" | c{r['copy']}"
    if when:
        line += ' | @' + when.astimezone().isoformat(timespec='seconds')
    return line
