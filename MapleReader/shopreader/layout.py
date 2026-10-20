"""Finding the shop list on screen by its colours, and measuring its rows."""
from PIL import Image, ImageChops, ImageOps
from .config import PRICE, ROW_BG, ROW_FADED
from .ocr import ocr_lines, pitch


def layout_from(pr, marks=None, old_h=None):
    """Shop layout from its price lines: list column(s), first/last row, row height.
    The row height is measured on every "... mesos" line (a misread price like "1 mesos" still marks a row)."""
    if not pr:
        return None
    h = pitch(marks or pr, default=None) or pitch(pr, default=None) or old_h or 56
    xs = sorted(l['x0'] for l in pr)
    groups = []
    for x in xs:                                     # lines starting a little left (a stray digit from the icon)
        if groups and x - groups[-1][-1] <= 0.7 * h:  # belong to the same column
            groups[-1].append(x)
        else:
            groups.append([x])
    cols = [max(set(g), key=lambda v: (g.count(v), v)) for g in groups]   # the usual start of a price line
    return dict(cols=cols, top=min(l['y0'] for l in pr), bottom=max(l['y1'] for l in pr), h=h,
                width=max(l['x1'] - l['x0'] for l in pr))


_SMALL = {'img': None, 'sm': None}


def _small(img, step):
    """The screenshot shrunk by `step`, made once per screenshot (several colour checks look at it)."""
    c = _SMALL                                      # (read once: "test a screenshot" may use this from another thread)
    if c['img'] is img:
        return c['sm']
    sm = img.resize((max(1, img.width // step), max(1, img.height // step)), Image.NEAREST)
    _SMALL.update(img=img, sm=sm)
    return sm


def color_boxes(img, col, tol=6, cell=24, minc=8, vgap=8):
    """Find areas of the screen filled with one UI colour. Very fast (no text reading): Pillow does the
    pixel work. Returns boxes (x0, y0, x1, y1), biggest first."""
    step = 4
    sm, c = _small(img, step), cell // step
    gw, gh = sm.width // c, sm.height // c
    if not gw or not gh:
        return []
    # 255 where a pixel is within `tol` of the colour on all three channels
    near = [band.point([255 if abs(v - k) <= tol else 0 for v in range(256)]) for band, k in zip(sm.split()[:3], col)]
    mask = ImageChops.multiply(ImageChops.multiply(near[0], near[1]), near[2])
    # average of each c x c cell; a cell is "dense" when at least 35% of its pixels match
    avg = mask.crop((0, 0, gw * c, gh * c)).resize((gw, gh), Image.BOX)
    need = c * c * 0.35
    flat = (getattr(avg, 'get_flattened_data', None) or avg.getdata)()
    dense = {(i % gw, i // gw) for i, v in enumerate(flat) if round(v * c * c / 255) >= need}
    comps, seen = [], set()
    steps = [(1, 0), (-1, 0)] + [(0, d) for d in range(-vgap, vgap + 1) if d]   # sold rows can leave vertical gaps
    for start in dense:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            q = stack.pop(); comp.append(q)
            for d in steps:
                r = (q[0] + d[0], q[1] + d[1])
                if r in dense and r not in seen:
                    seen.add(r); stack.append(r)
        if len(comp) >= minc:
            xs = [q[0] for q in comp]; ys = [q[1] for q in comp]
            comps.append((len(comp), (min(xs) * cell, min(ys) * cell, (max(xs) + 1) * cell, (max(ys) + 1) * cell)))
    return [b for _, b in sorted(comps, reverse=True)]


def blue_lists(img):
    """Blocks of the normal (blue) row colour wide enough to be a shop list (240 px and up at the usual size).
    Smaller blue patches are name tags and buttons, which grow big enough to count when the game is stretched."""
    return [b for b in color_boxes(img, ROW_BG, minc=3) if b[2] - b[0] >= 100]


def list_boxes(img):
    """Shop list areas: blocks of normal row colour, stretched over sold (faded) rows in the same column."""
    out = []
    faded = color_boxes(img, ROW_FADED, minc=4)
    for b in blue_lists(img)[:2]:
        x0, y0, x1, y1 = b
        for f in faded:
            if f[0] < x1 and f[2] > x0 and f[1] < y1 + 400 and f[3] > y0 - 400 and (f[2] - f[0]) < 2 * (x1 - x0) + 100:
                y0, y1 = min(y0, f[1]), max(y1, f[3])
        out.append((x0, y0, x1, y1))
    if not out:
        # every row showing is sold: no normal (blue) row to find the list by. A list of faded rows is a
        # tall block (6 rows high, about 5 wide: 1.2 times taller than wide, measured as 0.95 to 1.3 times on the
        # colour search's 24 px grid, depending on where the window is); wide strips (title bars, the Change Channel
        # window) and thin ones (scrollbar tracks) are something else.
        out = [f for f in faded if f[2] - f[0] >= 150 and f[3] - f[1] >= 0.9 * (f[2] - f[0])][:1]
    return out


def find_layout(img):
    """Find shop lists by their row colour and read them. Returns (layout, lines).
    layout['faded'] = the list was found by its sold rows only, so its faint text is read the way sold rows are."""
    L = []
    faded = not blue_lists(img)
    for b in list_boxes(img):
        L += read_box(img, (max(0, b[0] - 10), max(0, b[1] - 10), min(img.width, b[2] + 30), min(img.height, b[3] + 10)), faded)
    lay = fit_layout(L, None)
    if lay and faded:
        lay['faded'] = True
    return lay, L


def _orange(c):
    """True if the crop has the orange 'selected row' colour, so the extra red pass is worth it."""
    small = c.resize((max(1, c.width // 4), max(1, c.height // 4)))
    px = (getattr(small, 'get_flattened_data', None) or small.getdata)()   # newer Pillow renamed getdata
    return sum(1 for p in px if p[0] > 200 and 110 < p[1] < 200 and p[2] < 90) > 15


def read_list(img, lay, up=1.2, down=0.7):
    """Read only the list column(s): item names and prices. Much faster than reading the whole window."""
    h, L = lay['h'], []
    for x in lay['cols']:
        box = (max(0, x - 6), max(0, int(lay['top'] - up * h)), min(img.width, int(x + max(5.2 * h, lay['width'] + 0.6 * h))),
               min(img.height, int(max(lay['bottom'] + down * h, lay['top'] + 6.1 * h))))   # the list always shows 6 rows
        for l in read_box(img, box, lay.get('faded')):
            if not any(l['text'] == k['text'] and abs(l['y0'] - k['y0']) < 8 and abs(l['x0'] - k['x0']) < 30 for k in L):
                L.append(l)
    return L


def faded_threshold(crop):
    """Where to split a sold row's faint grey text from its near-white background: a little below the
    background's own grey (the commonest one), so brighter or darker screens work the same."""
    h = ImageOps.grayscale(crop).histogram()
    return max(range(256), key=lambda v: h[v]) - 20


def read_box(img, box, faded=False):
    """Read the text in one area; a second red-channel pass only if there's an orange (selected) row.
    faded=True: the area is sold rows only, so read their faint text split into black and white."""
    c = img.crop(box)
    got = ocr_lines(c, ox=box[0], oy=box[1], thr=faded_threshold(c) if faded else None)
    if _orange(c):
        for l in ocr_lines(c, red=True, ox=box[0], oy=box[1]):
            if not any(abs(l['y0'] - k['y0']) < 8 and abs(l['x0'] - k['x0']) < 25 for k in got):
                got.append(l)
    return got


def fit_layout(L, cand):
    """Layout from what was read: price lines give the columns, and every line containing "mesos"
    (even a misread one like "1 mesos") marks a row, so the true first and last rows are known."""
    pr = [l for l in L if PRICE.match(l['text'])]
    xs = {l['x0'] for l in pr}
    marks0 = [l for l in L if 'meso' in l['text'].lower() and any(abs(l['x0'] - x) < 40 for x in xs)]
    lay = layout_from(pr, marks0, cand and cand.get('h'))
    if not lay:
        return None
    # the gap from a name line down to its price line is ~0.42 of a row; if every visible row
    # has a faded (sold) row between it, the smallest price-to-price gap is two rows, not one
    dys = sorted(p['y0'] - n['y0'] for p in pr for n in L
                 if n is not p and not PRICE.match(n['text']) and abs(n['x0'] - p['x0']) < 30 and 8 < p['y0'] - n['y0'] < 0.7 * lay['h'])
    measured = any(sum(abs(p['x0'] - c) < 0.7 * lay['h'] for p in pr) >= 2 for c in lay['cols'])
    if dys:
        est = dys[len(dys) // 2] / 0.42
        if not measured:
            lay['h'] = int(round(est))               # one normal row only (the rest sold): use the name-to-price gap
        else:
            k = round(lay['h'] / est)
            if k >= 2:
                lay['h'] = int(round(lay['h'] / k))
    marks = [l for l in L if 'meso' in l['text'].lower() and any(abs(l['x0'] - c) < 0.45 * lay['h'] for c in lay['cols'])]
    lay['top'] = min(l['y0'] for l in marks)
    lay['bottom'] = max(l['y1'] for l in marks)
    return lay
