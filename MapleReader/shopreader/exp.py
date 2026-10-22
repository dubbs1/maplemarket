"""EXP tracker: reads your level and EXP off the game's status bar ("LV. 37" ... "EXP 93,499 [43.17%]") and works
out EXP per hour and when you'll level up. Screenshots only, like everything else.

ExpWatcher finds the status bar by the colours of its HP and MP bars (fast, no text reading), then re-reads the
EXP line every few seconds. The number is light grey on dark between green brackets, the level white digits on
orange tiles. Each character is cut out by its colour and compared with the game's digit shapes (exp_font.py, made
by tools/make_exp_font.py from test pictures): Tesseract slips on this small pixel font.
ExpTracker turns readings into totals, and drops readings that don't fit (a misread digit): within a level,
EXP / percentage is the EXP the level needs, which stays the same.
"""
import bisect
import json
import os
import re
import threading
import time
from PIL import Image, ImageOps
from .config import EXP_EVERY, EXP_IDLE, EXP_RUN_GAP, EXP_SEARCH_EVERY
from .layout import color_boxes
from . import engine
from .exp_font import GLYPHS

HP_RED, MP_BLUE = (204, 8, 0), (0, 124, 204)        # the status bar's HP and MP fill colours
MP_LOW = (0, 46, 70)           # the MP fill drawn dark navy (with a red outline) when MP is low
BAR_STEP = 169                 # from the HP fill's left edge to the MP fill's at the usual size (exact edges)

_white = lambda p: min(p) > 130 and max(p) - min(p) < 45           # the EXP number and the percentage digits
_green = lambda p: p[1] > 110 and p[1] - p[0] > 15 and p[1] - p[2] > 45   # the [ ] around the numbers (washed out by compression too)
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
    wide = lambda y: sum(min(px[x, y]) > 170 for x in range(x0, min(img.width, x1))) > 0.85 * (x1 - x0)
    # the first block tall enough to be letters (not the status bar's light border, which runs right across)
    run = next((r for r in _runs(rows) if r[1] - r[0] >= 4 and not all(wide(y) for y in range(r[0], r[1] + 1))), None)
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


_red = lambda p: p[0] > 150 and p[1] < 90 and p[2] < 90
_mp = lambda p: (p[2] > 130 and p[0] < 90) or (p[0] < 40 and p[2] > 45 and p[2] - p[1] > 15)   # blue, or low-MP navy


def _start(img, x, y0, y1, test):
    """The exact left edge of a bar's fill near x (the colour search's boxes are on an 8 px grid)."""
    px = img.load()
    for y in (y0 + y1) // 2, (y0 + 2 * y1) // 3, (2 * y0 + y1) // 3:
        if not 0 <= y < img.height:
            continue
        xs = [i for i in range(max(0, x - 12), min(img.width, x + 12)) if test(px[i, y])]
        if xs:
            return xs[0]
    return x


def find_bar(img):
    """Find the status bar by its HP bar (red) with the MP bar (blue) beside it: colour only, fast, at any interface
    size. Returns where its parts are, or None. The bars are measured from where their fills START (a fill always
    starts at its bar's left edge), so low HP or MP doesn't matter. Everything is measured in HP-bar widths: the
    texts are above the bars, the "EXP" label right of the MP bar, the level's tiles left of the HP bar."""
    reds = color_boxes(img, HP_RED, tol=40, cell=8, minc=4, vgap=1)[:6]
    blues = (color_boxes(img, MP_BLUE, tol=40, cell=8, minc=2, vgap=1)[:8] +
             color_boxes(img, MP_LOW, tol=30, cell=8, minc=2, vgap=1)[:8])
    for r in reds:
        bh = r[3] - r[1]
        rx = _start(img, r[0], r[1], r[3], _red)
        for b in blues:
            mx = _start(img, b[0], b[1], b[3], _mp)
            w = mx - rx                              # one bar's width (and the gap): HP's start to MP's start
            if not (abs(b[1] - r[1]) <= 8 and 5 * bh <= w <= 24 * bh and r[2] - r[0] <= w + 8 and b[2] - b[0] <= w + 8):
                continue                             # not the HP and MP bars side by side
            y, mp_end = r[1], mx + w
            area = (int(mp_end - 0.15 * w), max(0, int(y - 0.16 * w)), min(img.width, int(mp_end + 0.3 * w)), int(y + 0.02 * w))
            label = snug(img, area)
            if label == area or label[3] - label[1] < 6:
                continue                             # no white "EXP" letters where they should be
            lh = label[3] - label[1]
            return {'hp': (rx, r[1], mx - w // BAR_STEP, r[3]), 'mp': (mx, b[1], mp_end, b[3]), 'size': w / BAR_STEP,
                    'label': label, 'line': (max(0, label[1] - 2), min(img.height, label[3] + max(1, lh // 7))),
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
            if not dy:
                return [], _digit                    # a tile whose digit can't be seen (a window over it): unclear, not "3" for 38
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


def read_hp(img, bar):
    """(HP now, full HP) from the status bar's "HP [ 1146 / 1325 ]", or None if it can't be read cleanly."""
    t = _text(img, bar, 'hp')
    m = t and re.fullmatch(r'(\d{1,7})/(\d{1,7})', t)
    if not m or int(m[1]) > int(m[2]) or int(m[2]) < 1:
        return None
    return int(m[1]), int(m[2])


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
            if self.misses >= 5:                          # covered for a while (the mouse over it), or the window moved:
                self.misses = 0                           # look for it again, but keep the old place if it isn't found
                self.bar = find_bar(img) or self.bar     # (low MP, say: the old place is still right)
            return None
        self.misses = 0
        return {'exp': got[0], 'pct': got[1], 'level': read_level(img, self.bar), 'hp': read_hp(img, self.bar)}


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
    SLOT, SLOTS = 10 * 60, 12                            # the EXP page's chart: 10-minute slots, the last 2 hours

    KILL_MAX = 6                                         # kills of one mob that may hide in one reading (3 s)

    def __init__(self, on_gain=None, on_run=None, namer=None):
        self.lock = threading.Lock()
        self.on_gain = on_gain                           # called with each gain (n, time): the daily totals
        self.on_run = on_run                             # called with each finished run (a line for the EXP log)
        self.namer = namer                               # the mob that gives this much EXP (mobs.txt), or None
        self.map = None                                  # the map you're on, when known (for the EXP log)
        self.paused = None                               # when recording was stopped: the clock stands still
        self.reset()

    def pause(self, now=None):
        """Recording stopped: per hour, playing time and the charts stay as they were (not counting idle time)."""
        with self.lock:
            if self.paused is None:
                self.paused = time.time() if now is None else now

    def resume(self, now=None):
        """Recording again: the stopped time is left out, as if it never happened."""
        now = time.time() if now is None else now
        with self.lock:
            if self.paused is None:
                return
            gap, self.paused = max(0, now - self.paused), None
            self._shift(gap)
            self.first = None                            # (a reading from before the stop doesn't count as agreeing)

    def _shift(self, gap):
        """Leave out `gap` seconds (stopped, or idle): every time so far moves later, as if they never happened."""
        sh = lambda p: (p[0] + gap,) + tuple(p[1:])
        if self.start:
            self.start, self.last = sh(self.start), sh(self.last)
            self.history = [sh(h) for h in self.history]
            self.trail = [sh(h) for h in self.trail]
            self.gain_t += gap
            if self.run:
                self.run['t0'] += gap
                if self.run['mt0'] is not None:
                    self.run['mt0'] += gap
                    self.run['mt1'] += gap
            if self.mt0 is not None:
                self.mt0 += gap
                self.mt1 += gap

    def _close_run(self, end, gained):
        """The current run ends (a level-up, a long break, Reset, a new map, closing the app): log it."""
        r, self.run = self.run, None
        if not r:
            return
        mins, got = (end - r['t0']) / 60, gained - r['g0']
        if mins >= 1 and got > 0 and self.on_run:
            self.on_run({'date': r['wall'], 'minutes': round(mins), 'gained': got, 'per_hour': round(got / mins * 60),
                         'level': r['level'], 'map': r['map'], 'party': r['party'], 'mesos': r['mg'] if r['mt0'] is not None else None,
                         'mesos_per_hour': self._mph(r['mg'], r['mt0'], r['mt1']), 'kills': self._kill_list(r['kills']),
                         'kills_total': sum(r['kills'].values()), 'taken': r['taken'], 'hits': r['hits']})

    def _open_run(self, t, wall, gained, level):
        self.run = {'t0': t, 'wall': wall, 'g0': gained, 'level': level, 'map': self.map, 'party': None, 'mg': 0, 'mt0': None, 'mt1': None,
                    'kills': {}, 'taken': 0, 'hits': 0}

    # ---- kills: every EXP gain is one kill or several (the amount a mob gives never changes) ----
    def _kills(self, d):
        """`d` EXP came in since the last reading: which kills were they? An amount seen twice is a mob's EXP; a gain
        that is a multiple of one, or the sum of two, is those kills. (In a party the EXP is shared by damage dealt:
        the amounts are steady while your partner hunts elsewhere, and vary when you share mobs; the page folds
        amounts seen once into "other gains".)"""
        self.last_kills = []                         # (what this rise was taken as: the mob-picture catcher asks)
        known = sorted((a for a, n in self.amounts.items() if n >= 2), reverse=True)
        if d in known:
            return self._kill(d, 1)
        for a in known:
            if d % a == 0 and d // a <= self.KILL_MAX:
                return self._kill(a, d // a)
        for a in known:
            if d - a in known and d - a >= a:
                self._kill(a, 1)
                return self._kill(d - a, 1)
        self._kill(d, 1)

    def _kill(self, a, n):
        self.last_kills.append((a, n))
        self.amounts[a] = self.amounts.get(a, 0) + n
        if self.run:
            self.run['kills'][a] = self.run['kills'].get(a, 0) + n

    def _kill_list(self, kills):
        """[{exp, n, name}], most killed first (name None when the amount isn't in mobs.txt)."""
        out = [{'exp': a, 'n': n, 'name': self.namer(a) if self.namer else None} for a, n in kills.items()]
        return sorted(out, key=lambda k: -k['n'])

    def _hp(self, cur, full):
        """The HP numbers read: every drop since the last reading is damage taken (potions in between hide some)."""
        prev, self.hp = self.hp, (cur, full)
        if prev and prev[1] == full and cur < prev[0]:   # (a different full HP: a level-up, or a misread: not a hit)
            d = prev[0] - cur
            self.taken, self.hits, self.big = self.taken + d, self.hits + 1, max(self.big, d)
            if self.run:
                self.run['taken'] += d
                self.run['hits'] += 1

    def end_run(self, now=None):
        """Log the current run now (Reset, closing the app)."""
        now = time.time() if now is None else now
        with self.lock:
            if getattr(self, 'start', None):             # (nothing yet when first made)
                self._close_run(self._now(now), self.gained)

    def set_map(self, name, now=None):
        """The map changed: the EXP log starts a new entry there."""
        now = time.time() if now is None else now
        with self.lock:
            if name == self.map:
                return
            if self.start and self.run:
                end = self._now(now)
                self._close_run(end, self.gained)
                self.map = name
                self._open_run(end, now, self.gained, self.last[1])
            else:
                self.map = name

    MESO_JUMP = 5_000_000                                # a bigger rise between two looks is a misread, not a pickup

    def set_mesos(self, amount, now=None):
        """The Item window showed `amount` mesos. Every rise since the last look counts as mesos gained (spending
        doesn't take any off); mesos per hour is that over the time between the first and the last look."""
        now = time.time() if now is None else now
        with self.lock:
            if not self.start or self.paused is not None:
                self.mesos = amount                      # (just where it stands: nothing gained while not recording)
                return
            t = self._now(now)
            if self.mesos is not None and amount - self.mesos > self.MESO_JUMP:
                return                                   # a misread (no pickup is that big): nothing changes
            if self.mesos is not None and amount < self.mesos:
                if self.meso_low is None:                # lower: spent, or a digit lost (1,421,566 read as 421,566, which
                    self.meso_low = amount               # would make the next look a million "gained"): wait for a second
                    return                               # look; lower again = real, and what came in since then counts
                self.meso_gain += max(0, amount - self.meso_low)
                if self.run:
                    self.run['mg'] += max(0, amount - self.meso_low)
            elif self.mesos is not None and 0 < amount - self.mesos:
                self.meso_gain += amount - self.mesos
                if self.run:
                    self.run['mg'] += amount - self.mesos
            self.mesos, self.meso_low = amount, None     # (spending lowers it)
            self.mt0 = self.mt0 if self.mt0 is not None else t
            self.mt1 = t
            if self.run:
                self.run['mt0'] = self.run['mt0'] if self.run['mt0'] is not None else t
                self.run['mt1'] = t

    @staticmethod
    def _mph(gain, t0, t1):
        return round(gain / (t1 - t0) * 3600) if t0 is not None and t1 - t0 >= 300 else None

    def set_party(self, n):
        """The party window showed n members: the EXP log keeps the most seen in a run (None = solo or not shown)."""
        with self.lock:
            if self.run and n:
                self.run['party'] = max(self.run['party'] or 0, n)

    def _now(self, now):
        """The tracker's clock: it stands still while stopped, and after a minute with no EXP."""
        if self.paused is not None:
            now = min(now, self.paused)
        if self.start and now - self.gain_t > EXP_IDLE:
            now = self.gain_t + EXP_IDLE
        return now

    def reset(self):
        self.end_run()
        with self.lock:
            self.run = None                             # the EXP log's current entry
            self.mesos = None                           # the Item window's meso amount, last read
            self.meso_gain, self.mt0, self.mt1 = 0, None, None   # mesos gained, and when they were first and last read
            self.gain_t = None                          # the last time EXP went up (the tracker's clock)
            self.start = self.last = None               # first and latest accepted reading: (t, level, exp, pct)
            self.first = None                           # a first reading, until a second one agrees with it
            self.gained = self.lost = self.levels = 0
            self.need = None                            # EXP the current level needs (exp / pct)
            self.need_prev = None                       # the level before's (a loose check while the new one is unknown)
            self.meso_low = None                        # a lower meso amount seen once: real (spent) only if seen again
            self.amounts = {}                           # EXP per kill -> kills this session
            self.last_kills = []                        # the latest rise as kills: [(EXP, n)]
            self.hp = None                              # (HP now, full HP) last read
            self.taken = self.hits = self.big = 0       # damage taken, hits taken, the biggest hit
            self.history = []                           # (t, total gained) for the per-hour rate
            self.trail = []                             # (t, total gained) about once a minute, the whole session

    @staticmethod
    def _need_of(exp, pct):
        return exp * 100 / pct if pct >= 1 else None    # (below 1% the rounding of the % makes it too rough)

    def _fits(self, need, than):
        return than is None or need is None or abs(need / than - 1) < 0.03

    def _new_level_ok(self, exp, pct, need):
        """Just after a level-up, before the new level's EXP is known, a reading is kept only if the level it implies
        needs between half and 2.5 times what the level before did (a digit read wrong implies ten times more)."""
        if need is None:                                 # under 1%: the rounded % gives a lower bound only
            return exp * 100 / (pct + 0.005) <= self.need_prev * 2.5
        return 0.5 < need / self.need_prev < 2.5

    def add(self, r, now=None):
        """Feed a reading; True if it was accepted (it changed something)."""
        now = time.time() if now is None else now
        with self.lock:
            if self.paused is not None:                  # (a last reading arriving just after Stop)
                return False
            ok = self._add(r['exp'], r['pct'], r.get('level'), now)
            if r.get('hp') and self.start:
                self._hp(*r['hp'])
            return ok

    def _add(self, exp, pct, level, now):
        need = self._need_of(exp, pct)
        if self.last is None:                            # start once two readings agree (one could be a misread)
            f = self.first
            if f and f[2] <= exp and self._fits(need, self._need_of(f[2], f[3])):
                self.start = self.last = f
                self.need = self._need_of(f[2], f[3]) or need
                self.history, self.trail = [(f[0], 0)], [(f[0], 0)]
                self.gain_t = f[0]
                self._open_run(f[0], f[0], 0, f[1])
                self.first = None
                if (exp, pct) == (f[2], f[3]):
                    return True
            else:
                self.first = (now, level, exp, pct)
                return False
        _, lv0, exp0, pct0 = self.last
        g0 = self.gained
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
            self.need_prev, self.need = self.need or self.need_prev, need
            lv0 = lv0 + 1 if lv0 else None             # counted from the level known before, not re-read
        elif not fits:
            return False                                 # a misread: the number and the percentage disagree
        elif not self.need and self.need_prev and not self._new_level_ok(exp, pct, need):
            return False                                 # (just after a level-up: a misread here would be kept as the level's EXP)
        elif exp >= exp0:
            self.gained += exp - exp0
            if need and (pct >= 5 or not self.need):   # (just after a level-up the level's EXP isn't known yet)
                self.need = need                         # keep refining it (a bigger percentage is more exact)
        else:
            self.lost += exp0 - exp                     # EXP lost (from dying)
        if self.gained > g0:
            self._kills(self.gained - g0)
            idle = now - self.gain_t
            if idle > EXP_IDLE:                          # back after a break: the time without EXP doesn't count
                if idle > EXP_RUN_GAP:                   # (a long one starts a new EXP log entry)
                    self._close_run(self.gain_t + EXP_IDLE, g0)
                self._shift(idle - EXP_IDLE)
                if not self.run:
                    self._open_run(now, now, g0, lv0 or level)
            self.gain_t = now
        if up:                                           # a level-up starts a new EXP log entry
            self._close_run(now, self.gained)
            self._open_run(now, now, self.gained, lv0 or level)
        self.last = (now, lv0 or level, exp, pct)       # once known, the level changes only by levelling up
        self.history.append((now, self.gained))
        self.history = [h for h in self.history if now - h[0] <= self.RECENT] or [(now, self.gained)]
        if len(self.trail) >= 2 and now - self.trail[-2][0] < 60:
            self.trail[-1] = (now, self.gained)          # (one point a minute is plenty for the charts)
        else:
            self.trail.append((now, self.gained))
        if self.on_gain and self.gained > g0:
            self.on_gain(self.gained - g0, now)
        return True

    def _at(self, t, ts=None):
        """Total gained at time t (from the trail; `ts` = the trail's times, when the caller has them)."""
        i = bisect.bisect_right(ts if ts is not None else [p[0] for p in self.trail], t)
        return self.trail[i - 1][1] if i else 0

    def _hours(self, now):
        """The last 2 hours in 10-minute slots (oldest first), the last hour, the hour before, the best hour."""
        t0 = self.start[0]
        ts = [p[0] for p in self.trail]                  # (once: summary() runs every second, the trail grows all day)
        at = lambda t: self._at(t, ts)
        n = min(self.SLOTS, max(1, -int(-(now - t0) // self.SLOT)))
        edges = [max(t0, now - (n - k) * self.SLOT) for k in range(n)] + [now]
        slots = [at(b) - at(a) for a, b in zip(edges, edges[1:])]
        whole = now - t0
        hour = self.gained - at(now - 3600) if whole >= 3600 else None
        prev = at(now - 3600) - at(now - 7200) if whole >= 7200 else None
        best = None
        if whole >= 3600:
            ends = [t for t in ts if t >= t0 + 3600] + [now]
            best = max(at(t) - at(t - 3600) for t in ends)
        return slots, hour, prev, best

    def summary(self, now=None):
        """What the window shows, or None before the first readings."""
        real = time.time() if now is None else now
        with self.lock:
            if self.last is None:
                return None
            now = self._now(real)
            t0, g0 = self.history[0]
            span = now - t0
            recent = (self.gained - g0) / span * 3600 if span >= 60 else None
            whole = now - self.start[0]
            per_hour = recent if recent is not None else (self.gained / whole * 3600 if whole >= 60 else None)
            _, level, exp, pct = self.last
            need = round(self.need) if self.need else None
            left = need - exp if need else None
            eta = left / per_hour * 3600 if left and per_hour and per_hour > 0 else None
            slots, hour, prev, best = self._hours(now)
            r = self.run
            run = r and {'minutes': round((now - r['t0']) / 60), 'gained': self.gained - r['g0'], 'map': r['map'], 'level': level,
                         'party': r['party'], 'mesos_per_hour': self._mph(r['mg'], r['mt0'], r['mt1']),
                         'kills': self._kill_list(r['kills']), 'kills_total': sum(r['kills'].values()), 'taken': r['taken'], 'hits': r['hits'],
                         'per_hour': round((self.gained - r['g0']) / (now - r['t0']) * 3600) if now - r['t0'] >= 60 else None}
            return {'slots': slots, 'hour': hour, 'prev_hour': prev, 'best_hour': best, 'run': run, 'mesos': self.mesos,
                    'mesos_gained': self.meso_gain if self.mt0 is not None else None, 'mesos_per_hour': self._mph(self.meso_gain, self.mt0, self.mt1),
                    'last5': (self.gained - self._at(now - 300)) * 12 if whole >= 300 else None,
                    'idle': self.paused is None and real - self.gain_t > EXP_IDLE, 'stopped': self.paused is not None,
                    'level': level, 'exp': exp, 'pct': pct, 'need': need, 'left': left,
                    'gained': self.gained, 'lost': self.lost, 'levels': self.levels,
                    'kills': self._kill_list(self.amounts), 'kills_total': sum(self.amounts.values()),
                    'taken': self.taken, 'hits': self.hits, 'big': self.big, 'hp': self.hp,
                    'per_hour': round(per_hour) if per_hour is not None else None,
                    'pct_per_hour': round(per_hour / self.need * 100, 2) if per_hour is not None and self.need else None,
                    'eta': round(eta) if eta is not None else None, 'eta_text': _fmt_eta(eta),
                    'minutes': round(whole / 60), 'seen': self.last[0]}


class ExpDays:
    """EXP gained each day, kept for 30 days in scans/exp_days.json (the EXP page's "Last 7 days" and "Today")."""
    KEEP = 30

    def __init__(self, path):
        self.path, self.lock, self.saved = path, threading.Lock(), 0
        try:
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
            self.days = {k: int(v) for k, v in d.items() if re.fullmatch(r'\d{4}-\d\d-\d\d', k)}
        except Exception:
            self.days = {}

    def add(self, n, now=None):
        now = time.time() if now is None else now
        if n <= 0:
            return
        day = time.strftime('%Y-%m-%d', time.localtime(now))
        with self.lock:
            self.days[day] = self.days.get(day, 0) + int(n)
            if now - self.saved >= 60:                # written at most once a minute (and when the app closes)
                self._save(now)

    def last(self, n=7, now=None):
        """The last n days, oldest first, today last: [{'day': '2026-10-21', 'gained': 1234}, ...]."""
        now = time.time() if now is None else now
        with self.lock:
            out = []
            for k in range(n - 1, -1, -1):
                day = time.strftime('%Y-%m-%d', time.localtime(now - k * 86400))
                out.append({'day': day, 'gained': self.days.get(day, 0)})
            return out

    def flush(self):
        with self.lock:
            self._save(time.time())

    def _save(self, now):
        self.saved = now
        self.days = dict(sorted(self.days.items())[-self.KEEP:])
        try:
            os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.days, f)
            os.replace(tmp, self.path)
        except OSError:
            pass                                      # (a full or read-only disk: the totals stay in memory)


class ExpLog:
    """The EXP log: one line per run (one map and level, until a level-up, a long break or a new map), newest first,
    kept in scans/exp_log.json. Each line can be renamed or deleted from the EXP tab."""
    KEEP = 300

    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()
        try:
            with open(path, encoding='utf-8') as f:
                self.items = [e for e in json.load(f) if isinstance(e, dict) and 'id' in e][:self.KEEP]
        except Exception:
            self.items = []

    def add(self, e):
        with self.lock:
            e = dict(e, id='%x' % int(e['date'] * 1000))
            self.items.insert(0, e)
            del self.items[self.KEEP:]
            self._save()
            return e

    def rename(self, id, name):
        with self.lock:
            for e in self.items:
                if e['id'] == id:
                    e['name'] = str(name or '').strip()[:40] or None
                    self._save()
                    return True
            return False

    def delete(self, id):
        with self.lock:
            n = len(self.items)
            self.items = [e for e in self.items if e['id'] != id]
            if len(self.items) < n:
                self._save()
            return len(self.items) < n

    def list(self, n=50):
        with self.lock:
            return [dict(e) for e in self.items[:n]]

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.items, f)
            os.replace(tmp, self.path)
        except OSError:
            pass                                      # (a full or read-only disk: kept in memory)
