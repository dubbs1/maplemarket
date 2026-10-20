"""EXP tracker: reads your level and EXP off the game's status bar ("LV. 37" ... "EXP 93,499 [43.17%]") and works
out EXP per hour and when you'll level up. Screenshots only, like everything else.

ExpWatcher finds the status bar by the colours of its HP and MP bars (fast, no text reading), then re-reads the
EXP line every few seconds. The number is light grey on dark between green brackets, the level white digits on
orange tiles. Each character is cut out by its colour and compared with the game's digit shapes (exp_font.py, made
by tools/make_exp_font.py from test pictures): Tesseract slips on this small pixel font.
ExpTracker turns readings into totals, and drops readings that don't fit (a misread digit): within a level,
EXP / percentage is the EXP the level needs, which stays the same.
"""
import re
import threading
import time
from PIL import Image, ImageOps
from .config import EXP_EVERY, EXP_SEARCH_EVERY
from .layout import color_boxes
from . import engine
from .exp_font import GLYPHS

HP_RED, MP_BLUE = (204, 8, 0), (0, 124, 204)        # the status bar's HP and MP fill colours
HP_BAR = 168                   # width (px) of the HP bar at the usual interface size

_white = lambda p: min(p) > 130 and max(p) - min(p) < 45           # the EXP number and the percentage digits
_green = lambda p: p[1] > 110 and p[1] - p[0] > 30 and p[1] - p[2] > 60   # the [ ] around the numbers
# (not the EXP bar's yellow-green fill below it, which has as much red as green)
_digit = lambda p: p[2] > 120 and p[1] > 150     # the level's white digits (the orange tile has almost no blue)
_tile = lambda p: p[0] > 200 and 90 < p[1] < 190 and p[2] < 90     # the orange tiles the level's digits sit on

FONT_OF = {'hp': 'small', 'mp': 'small', 'exp': 'small', 'pct': 'small', 'level': 'tile'}


def _runs(xs, gap=1):
    """[first, last] of each block of consecutive numbers (allowing `gap`)."""
    out = []
    for x in xs:
        if out and x - out[-1][1] <= gap:
            out[-1][1] = x
        else:
            out.append([x, x])
    return out


def snug(img, box):
    """The "EXP" label's box trimmed to its letters (the search box can take in the bar below it)."""
    x0, y0, x1, y1 = box
    px = img.load()
    rows = [y for y in range(max(0, y0 - 2), min(img.height, y1 + 2))
            if any(min(px[x, y]) > 170 for x in range(x0, min(img.width, x1)))]
    run = next((r for r in _runs(rows) if r[1] - r[0] >= 4), None)   # the first tall enough to be letters
    if not run:
        return box
    ys, ye = run[0], run[1] + 1
    cols = [x for x in range(x0, min(img.width, x1 + (ye - ys))) if any(min(px[x, y]) > 170 for y in range(ys, ye))]
    xe = cols[0] if cols else x1
    for x in cols:                                   # the letters, up to the first wide gap after them
        if x - xe > max(2, (ye - ys) // 3):
            break
        xe = x
    return (x0, ys, xe + 1, ye)


def find_bar(img):
    """Find the status bar by its HP bar (red) with the MP bar (blue) right beside it, the same size: colour only,
    fast, at any interface size. Returns where its parts are, or None. Everything is measured in HP-bar widths:
    the texts are above the bars, the "EXP" label right of the MP bar, the level's tiles left of the HP bar."""
    reds = color_boxes(img, HP_RED, tol=40, cell=8, minc=4, vgap=1)[:6]
    blues = color_boxes(img, MP_BLUE, tol=40, cell=8, minc=4, vgap=1)[:6]
    for r in reds:
        w, bh = r[2] - r[0], r[3] - r[1]
        if w < 4 * bh:
            continue                                 # not bar-shaped
        for b in blues:
            if abs(b[1] - r[1]) <= 8 and 0 <= b[0] - r[2] <= 24 and 0.8 <= (b[2] - b[0]) / w <= 1.25:
                y = r[1]
                area = (b[2], max(0, int(y - 0.2 * w)), min(img.width, int(b[2] + 0.3 * w)), int(y + 0.02 * w))
                label = snug(img, area)
                if label == area or label[3] - label[1] < 6:
                    continue                         # no white "EXP" letters where they should be
                lh = label[3] - label[1]
                return {'hp': r, 'mp': b, 'size': w / HP_BAR, 'label': label,
                        'line': (max(0, label[1] - 2), min(img.height, label[3] + max(1, lh // 7))),
                        'level': (max(0, int(r[0] - 2.0 * w)), max(0, int(y - 0.2 * w)), max(1, int(r[0] - 1.1 * w)),
                                  min(img.height, int(y + 0.15 * w)))}
    return None


def _ink_rows(px, a, b, y0, y1, test):
    """Rows y0..y1 trimmed to those with ink in columns a..b (None if there's none)."""
    ys = [y for y in range(y0, y1) if any(test(px[x, y]) for x in range(a, b + 1))]
    return (ys[0], ys[-1] + 1) if ys else None


def _boxes(img, bar, part):
    """Where each character of one text on the status bar is, left to right, and the colour test for its ink:
    'hp' and 'mp' (the numbers inside their [ ]), 'exp' (the number after the label), 'pct' (inside the [ ] after
    it) or 'level' (one digit per orange tile). A character is a block of columns with ink."""
    px, size = img.load(), bar['size']
    if part == 'level':
        x0, y0, x1, y1 = bar['level']
        cols = [x for x in range(x0, x1) if sum(_tile(px[x, y]) for y in range(y0, y1)) >= max(2, 4 * size)]
        out = []
        for a, b in [t for t in _runs(cols) if t[1] - t[0] >= 6 * size][:3]:     # a level has 1 to 3 digits
            ty = _ink_rows(px, a, b, y0, y1, _tile)
            dx = [x for x in range(a, b + 1) if any(_digit(px[x, y]) for y in range(*ty))]
            dy = dx and _ink_rows(px, dx[0], dx[-1], ty[0], ty[1], _digit)
            if dy:
                out.append((dx[0], dy[0], dx[-1] + 1, dy[1]))
        return out, _digit
    y0, y1 = bar['line']
    if part in ('hp', 'mp'):
        x0, x1 = bar[part][0], bar[part][2]
    else:
        lh = bar['label'][3] - bar['label'][1]
        x0, x1 = bar['label'][2] + 1, min(img.width, bar['label'][2] + 13 * lh)
    greens = _runs([x for x in range(x0, x1) if any(_green(px[x, y]) for y in range(y0, y1))])
    if part == 'exp':
        if not greens:
            return [], _white
        a, b = x0, greens[0][0] - 1
    else:
        if len(greens) < 2:
            return [], _white
        a, b = greens[0][1] + 2, greens[1][0] - 1    # a pixel clear of each bracket: its soft edge isn't ink
    out = []
    for c0, c1 in _runs([x for x in range(a, b) if any(_white(px[x, y]) for y in range(y0, y1))]):
        ys = _ink_rows(px, c0, c1, y0, y1, _white)
        if c1 == c0 and ys[1] - ys[0] >= 6 * size:
            continue                                 # a thin sliver: the bracket's or the label's soft edge
        out += _split(img, (c0, ys[0], c1 + 1, ys[1]))
    return out, _white


def _split(img, box):
    """A block much wider than tall is two characters touching (blurred together at some interface sizes): split
    it at its faintest column near the middle."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w <= 1.3 * h or h < 4:
        return [box]
    m = _shade(img, box, 'text').load()
    ink = {x: sum(m[x, y] for y in range(h)) for x in range(w // 4, w - w // 4)}
    cut = min(ink, key=lambda x: (ink[x], abs(x - w / 2)))
    out = []
    for a, b in ((x0, x0 + cut), (x0 + cut + 1, x1)):
        if b <= a:
            continue
        part = _shade(img, (a, y0, b, y1), 'text').load()
        ys = [y for y in range(h) if any(part[x, y] >= 128 for x in range(b - a))]
        if ys:
            out += _split(img, (a, y0 + ys[0], b, y0 + ys[-1] + 1))
    return out


def glyphs_of(img, bar, part):
    """The characters of one text on the status bar (see _boxes), each as rows of shades '0' (none) to '9' (ink)."""
    out = []
    for box in _boxes(img, bar, part)[0]:
        m = _shade(img, box, part).load()
        out.append([''.join(str(m[x, y] * 9 // 255) for x in range(box[2] - box[0])) for y in range(box[3] - box[1])])
    return out


def _shade(img, box, part):
    """A character's ink as shades, 0 (background) to 255 (surely ink), measured against the darkest and brightest
    pixels in its box: kinder than yes/no to blurry text, and the same on lighter or darker backgrounds."""
    if part == 'level':
        v = [p[2] for p in img.crop(box).getdata()]   # white digits on orange: blue tells them apart
    else:
        v = [min(p) if max(p) - min(p) < 70 else 0 for p in img.crop(box).getdata()]
    lo, hi = min(v), max(v)
    lo += (hi - lo) // 4
    m = Image.new('L', (box[2] - box[0], box[3] - box[1]))
    m.putdata([max(0, min(255, (p - lo) * 255 // max(1, hi - lo))) for p in v])
    return m


_shapes = {}


def _shapes_of(sample, w, h):
    """A known shape as the game would draw it w x h: shrunk or grown, and (as the game's pixels may fall a third
    of a pixel either way) drawn at a few small offsets, each trimmed to its ink again. Brightest ink = 255."""
    key = (sample, w, h)
    if key not in _shapes:
        if len(_shapes) > 4000:
            _shapes.clear()                              # (sizes seen across many resizes)
        sw, sh = len(sample[0]), len(sample)
        m = Image.new('L', (sw, sh))
        m.putdata([int(c) * 255 // 9 for r in sample for c in r])
        m = ImageOps.expand(m, border=2, fill=0)
        kx, ky = sw / w, sh / h                          # source pixels per drawn pixel
        out = []
        for ox in (0, 1 / 3, 2 / 3):
            for oy in (0, 1 / 3, 2 / 3):
                d = m.transform((w + 3, h + 3), Image.AFFINE, (kx, 0, 2 - kx * (1 + ox), 0, ky, 2 - ky * (1 + oy)),
                                Image.BILINEAR)
                bb = d.point(lambda p: 255 if p >= 64 else 0).getbbox()
                if bb:
                    d = d.crop(bb).resize((w, h), Image.BILINEAR)
                v = list(d.getdata())
                top = max(v) or 1
                out.append([p * 255 / top for p in v])
        _shapes[key] = out
    return _shapes[key]


def _apart(v, t):
    return sum(abs(a - b) for a, b in zip(v, t)) / (255 * len(v))


def classify(m, font):
    """The character the shades `m` look most like among the known shapes; None when no shape is close (a character
    not known yet), '' when it's too blurred to tell which. When two are close (3 and 9 differ in a few pixels),
    only the pixels where those two differ decide."""
    w, h = m.size
    v = list(m.getdata())
    best = []
    for ch, samples in GLYPHS.get(font, {}).items():
        if ch not in ',.':                           # dots and commas are told by their size instead
            best.append(min((min(_apart(v, t) for t in _shapes_of(s, w, h)) + abs(w / h - len(s[0]) / len(s)) / 4,
                             ch, s) for s in samples))
    best.sort()
    if not best or best[0][0] > MATCH:
        return None
    if font == 'tile' and (best[0][0] > TILE_MATCH or (len(best) > 1 and best[1][0] - best[0][0] < 0.05)):
        return ''                                    # the level's font: only some digits are known, so no near guesses
    if len(best) > 2 and best[2][0] - best[0][0] < 0.02:
        return ''                                    # three about as close: too blurred to tell
    if len(best) > 1 and best[1][0] - best[0][0] < 0.06:
        ta, tb = (min(_shapes_of(b[2], w, h), key=lambda t: _apart(v, t)) for b in best[:2])
        key = [i for i in range(len(v)) if abs(ta[i] - tb[i]) > 90]
        da, db = (sum(abs(v[i] - t[i]) for i in key) for t in (ta, tb))
        if not key or abs(da - db) < 0.2 * max(da, db):
            return ''                                # can't tell them apart
        return best[0][1] if da < db else best[1][1]
    return best[0][1]


MATCH = 0.3                    # how different (0-1) a character may be from its known shape
TILE_MATCH = 0.14              # the same for the level's digits (known ones match within 0.13; 3 and 8 are 0.13+ apart)


def _text(img, bar, part):
    boxes, _ = _boxes(img, bar, part)
    tall = max((b[3] - b[1] for b in boxes), default=0)
    out = ''
    for box in boxes:
        if box[3] - box[1] < tall * 0.45:
            # a dot or comma: a separator in the EXP, the decimal point in the % (a comma's tail can come apart)
            out += '' if out.endswith('.') else '.'
            continue
        ch = classify(_shade(img, box, part), FONT_OF[part])
        if ch is None and part != 'level':           # (Tesseract reads the level's font poorly: no guess there)
            ch = _guess(img, box, part)
        if not ch:
            return None                              # unclear: skip this reading (the next is a few seconds away)
        out += ch
    return out


def _guess(img, box, part):
    """A character none of the known shapes match (e.g. a digit no test picture showed yet): Tesseract reads it."""
    m = ImageOps.invert(_shade(img, box, part))
    m = ImageOps.expand(m.resize((m.width * 4, m.height * 4), Image.BICUBIC), border=16, fill=255)
    got = engine.text(m, config='--psm 10 -c tessedit_char_whitelist=0123456789').strip()
    return got if len(got) == 1 else None


def read_exp(img, bar):
    """(exp, percent) from the status bar, or None if it can't be read cleanly."""
    num, pct = _text(img, bar, 'exp'), _text(img, bar, 'pct')
    if not num or not pct:
        return None
    num, pct = num.replace('.', ''), pct.rstrip('%')
    if not num.isdigit() or not re.fullmatch(r'\d{1,3}(\.\d{1,3})?', pct):
        return None
    p = float(pct)
    return (int(num), p) if p < 100 else None


def read_level(img, bar):
    """The level (white digits on orange tiles), or None."""
    t = _text(img, bar, 'level')
    return int(t) if t and t.isdigit() and 1 <= int(t) <= 300 else None


class ExpWatcher:
    """Remembers where the status bar is and re-reads it every few seconds."""
    def __init__(self):
        self.bar = None
        self.misses, self.last_read, self.last_search = 0, 0, 0

    def find(self, img):
        self.bar = find_bar(img)
        return bool(self.bar)

    def update(self, img, now=None):
        """A reading {'exp', 'pct', 'level'} when it's time to look and it reads cleanly, else None."""
        now = time.time() if now is None else now
        if not self.bar:
            if now - self.last_search < EXP_SEARCH_EVERY:
                return None
            self.last_search = now
            if not self.find(img):
                return None
        if now - self.last_read < EXP_EVERY:
            return None
        self.last_read = now
        got = read_exp(img, self.bar)
        if got is None:
            self.misses += 1
            if self.misses >= 5:                          # covered for a while, or the window moved: search again
                self.bar, self.misses = None, 0
            return None
        self.misses = 0
        return {'exp': got[0], 'pct': got[1], 'level': read_level(img, self.bar)}


def _fmt_eta(seconds):
    if seconds is None:
        return None
    m = int(seconds // 60)
    if m >= 24 * 60:
        return f'{m // 1440} d {m % 1440 // 60} h'   # (short enough for the EXP card)
    return f'{m // 60} h {m % 60} min' if m >= 60 else f'{max(1, m)} min'


class ExpTracker:
    """EXP gained this session, per hour, and time to the next level, from readings that fit together.
    Safe to use from two threads (the scanner adds, the window asks for the summary)."""
    RECENT = 10 * 60                                     # "per hour" from the last 10 minutes

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.start = self.last = None               # first and latest accepted reading: (t, level, exp, pct)
            self.first = None                           # a first reading, until a second one agrees with it
            self.gained = self.lost = self.levels = 0
            self.need = None                            # EXP the current level needs (exp / pct)
            self.history = []                           # (t, total gained) for the per-hour rate

    @staticmethod
    def _need_of(exp, pct):
        return exp * 100 / pct if pct >= 1 else None    # (below 1% the rounding of the % makes it too rough)

    def _fits(self, need, than):
        return than is None or need is None or abs(need / than - 1) < 0.03

    def add(self, r, now=None):
        """Feed a reading; True if it was accepted (it changed something)."""
        now = time.time() if now is None else now
        with self.lock:
            return self._add(r['exp'], r['pct'], r.get('level'), now)

    def _add(self, exp, pct, level, now):
        need = self._need_of(exp, pct)
        if self.last is None:                            # start once two readings agree (one could be a misread)
            f = self.first
            if f and f[2] <= exp and self._fits(need, self._need_of(f[2], f[3])):
                self.start = self.last = f
                self.need = self._need_of(f[2], f[3]) or need
                self.history = [(f[0], 0)]
                self.first = None
                if (exp, pct) == (f[2], f[3]):
                    return True
            else:
                self.first = (now, level, exp, pct)
                return False
        _, lv0, exp0, pct0 = self.last
        if exp == exp0 and pct == pct0:
            if level and not lv0:
                self.last = (now, level, exp, pct)       # the level, read for the first time
                return True
            return False
        fits = self._fits(need, self.need)
        # levelled up: the EXP went down and no longer fits the old level (a death keeps the same level's EXP) but
        # a bigger one (or the level read one higher); just after a level-up the % is too small to tell, so a drop
        # from 50% or more to under 1% counts (a death costs far less)
        up = exp < exp0 and pct < pct0 and (
            (need is None and pct0 >= 50) or
            (need is not None and not fits and ((level and lv0 and level == lv0 + 1) or not self.need or need > self.need * 1.03)))
        if up:                                           # levelled up: the rest of the old level, then the new
            if self.need:
                self.gained += max(0, round(self.need) - exp0) + exp
            self.levels += 1
            self.need = need
            lv0 = lv0 + 1 if lv0 else None             # counted from the level known before, not re-read
        elif not fits:
            return False                                 # a misread: the number and the percentage disagree
        elif exp >= exp0:
            self.gained += exp - exp0
            if need and (pct >= 5 or not self.need):   # (just after a level-up the level's EXP isn't known yet)
                self.need = need                         # keep refining it (a bigger percentage is more exact)
        else:
            self.lost += exp0 - exp                     # EXP lost (from dying)
        self.last = (now, lv0 or level, exp, pct)       # once known, the level changes only by levelling up
        self.history.append((now, self.gained))
        self.history = [h for h in self.history if now - h[0] <= self.RECENT] or [(now, self.gained)]
        return True

    def summary(self, now=None):
        """What the window shows, or None before the first readings."""
        now = time.time() if now is None else now
        with self.lock:
            if self.last is None:
                return None
            t0, g0 = self.history[0]
            span = now - t0
            recent = (self.gained - g0) / span * 3600 if span >= 60 else None
            whole = now - self.start[0]
            per_hour = recent if recent is not None else (self.gained / whole * 3600 if whole >= 60 else None)
            _, level, exp, pct = self.last
            need = round(self.need) if self.need else None
            left = need - exp if need else None
            eta = left / per_hour * 3600 if left and per_hour and per_hour > 0 else None
            return {'level': level, 'exp': exp, 'pct': pct, 'need': need, 'left': left,
                    'gained': self.gained, 'lost': self.lost, 'levels': self.levels,
                    'per_hour': round(per_hour) if per_hour is not None else None,
                    'pct_per_hour': round(per_hour / self.need * 100, 2) if per_hour is not None and self.need else None,
                    'eta': round(eta) if eta is not None else None, 'eta_text': _fmt_eta(eta),
                    'minutes': round(whole / 60), 'seen': self.last[0]}
