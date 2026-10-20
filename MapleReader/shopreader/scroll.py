"""Keeps track of where you are in a long shop list, using the scrollbar handle.

Why: a shop selling many identical listings (say 14 x "Screw, 1 for 299 mesos") looks the same after you
scroll. Without knowing the scroll position the reader can't tell rows it saw before from new ones.

How: the game's handle has a fixed size and moves evenly from top (first row showing) to bottom (last
row showing). So for a list of N rows, a view whose handle sits a fraction f of the way down starts at
row round(f * (N - 6)). N is unknown, so the reader tries every N and keeps the ones where all the
views agree (the same slot never holds two different items). Different items pin N down exactly; for
a shop of only identical rows, the size of one mouse-wheel step decides, and if even that is unknown
the smallest N that fits is used, so it never counts more than it saw.
"""
from PIL import Image, ImageOps

VISIBLE = 6                    # rows a shop window shows at once
MAX_ROWS = 120                 # longest shop list considered
SLACK = 2                      # pixels of up/down give when comparing icons
ICON_SAME = 5                  # icons closer than this (0-255 average difference) count as the same

_blue = lambda p: p[2] - p[0] > 25 and p[2] > 90
_grey = lambda p: max(p) - min(p) <= 6 and 215 <= p[0] <= 240


def _runs(img, x, y0, y1):
    """Runs of the same kind of pixel down one column: [kind, start, length]; B blue, g track grey."""
    out, cur = [], None
    for y in range(y0, y1):
        p = img.getpixel((x, y))
        k = 'B' if _blue(p) else 'g' if _grey(p) else '.'
        if cur and cur[0] == k:
            cur[2] += 1
        else:
            cur = [k, y, 1]
            out.append(cur)
    return out


def find_scrollbar(img, lay, x=None):
    """(x, handle top below the up arrow in px, free px the handle can travel), or None if no handle."""
    h, x0 = lay['h'], lay['cols'][-1]
    y0, y1 = max(0, int(lay['top'] - 1.3 * h)), min(img.height, int(lay['top'] + 6.3 * h))
    xs = [x] if x else range(int(x0 + 3.6 * h), min(img.width - 1, int(x0 + 5 * h)))
    arrow = lambda r: r[0] == 'B' and 0.19 * h <= r[2] <= 0.35 * h
    for cx in xs:
        sig = [r for r in _runs(img, cx, y0, y1) if r[2] >= 3 and r[0] != '.']
        for a in (i for i, r in enumerate(sig) if arrow(r)):
            # up arrow, then track (grey, cut by the handle), then down arrow, all touching
            end = a + 1
            while end < len(sig) and sig[end][1] - (sig[end - 1][1] + sig[end - 1][2]) <= 6:
                end += 1
            downs = [j for j in range(a + 1, end) if arrow(sig[j])
                     and not any(r[0] == 'g' and r[2] >= 0.25 * h for r in sig[j + 1:end])]
            if not downs:
                continue
            b = downs[0]
            if sum(r[2] for r in sig[a + 1:b] if r[0] == 'g') < 1.5 * h:
                continue
            inner = [r for r in sig[a + 1:b] if r[0] == 'B']
            if not inner:
                return None                          # a scrollbar without a handle: everything fits
            top, end_ = inner[0][1], inner[-1][1] + inner[-1][2]   # handle may be drawn in pieces
            if end_ - top > 1.2 * h:
                continue
            start = sig[a][1] + sig[a][2]
            return cx, top - start, (sig[b][1] - start) - (end_ - top)
    return None


def _icon(img, x, y, h):
    """The item icon with its stack number (100, 46...) as 12x12 greys, cut at a few heights, because rows
    sit a pixel or two higher or lower at different spots."""
    out = []
    for dy in range(-SLACK, SLACK + 1):
        box = (max(0, int(x - 1.15 * h)), max(0, int(y - 0.5 * h) + dy), max(1, int(x - 0.1 * h)),
               min(img.height, int(y + 0.4 * h) + dy))
        g = ImageOps.grayscale(img.crop(box)).resize((12, 12), Image.BILINEAR)
        out.append(list((getattr(g, 'get_flattened_data', None) or g.getdata)()))
    return out


class ScrollTracker:
    """One shop visit. Call reset() when a different shop opens."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = None              # scrollbar column
        self.margin = None         # handle position when the list was at the top
        self.free = None           # how far the handle can travel
        self.wheel = None          # smallest handle move seen between two screenshots (one wheel notch)
        self.last_seen = None
        self.views = []            # (fraction down the list, {visible row: (text, icon, row)})
        self.rows_n = VISIBLE
        self._gaps = {}

    def _bar(self, img, lay):
        sb = find_scrollbar(img, lay, self.x) or (find_scrollbar(img, lay) if self.x else None)
        if not sb:
            return None
        self.x, rel, self.free = sb
        if self.margin is None or rel < self.margin:
            self.margin = rel                        # a shop always opens scrolled to the top
        return rel - self.margin

    def observe(self, img, lay):
        """Every screenshot, even mid-scroll: the smallest handle move is about one wheel notch."""
        if not lay or len(lay['cols']) != 1:
            return
        p = self._bar(img, lay)
        if p is None:
            return
        if self.last_seen is not None and abs(p - self.last_seen) >= 2:
            d = abs(p - self.last_seen)
            self.wheel = d if self.wheel is None else min(self.wheel, d)
        self.last_seen = p

    # --- matching rows ---
    def _same(self, a, b):
        if a[0] != b[0]:
            return False
        key = (id(a), id(b))
        if key not in self._gaps:
            ref = b[1][SLACK]
            self._gaps[key] = min(sum(abs(p - q) for p, q in zip(v, ref)) / len(ref) for v in a[1])
        return self._gaps[key] <= ICON_SAME

    def _layout(self, n):
        """Slot map if the list had n rows: {slot: entry}, and how many places the views disagree."""
        slots, clash = {}, 0
        for f, view in self.views:
            off = round(f * (n - VISIBLE))
            for i, e in view.items():
                old = slots.get(off + i)
                if old is not None and not self._same(old, e):
                    clash += 1
                slots[off + i] = e                   # the newest look at a slot wins
        return slots, clash

    def _solve(self):
        if not any(f for f, _ in self.views):
            return VISIBLE                           # never scrolled
        tried = [(n, self._layout(n)[1]) for n in range(VISIBLE + 1, MAX_ROWS + 1)]
        best = min(c for _, c in tried)
        fits = [n for n, c in tried if c == best]
        if self.wheel and self.free and self.margin is not None:
            guess = VISIBLE + (self.free - 2 * self.margin) / self.wheel      # if one notch = one row
            close = [n for n in fits if n <= guess + 0.5]
            return max(close) if close else min(fits)
        return min(fits)                             # unsure: the smallest list that fits

    def place(self, img, lay, rows):
        """Remember this view. Returns every row of the shop seen so far in this visit, each with
        r['copy'] = 1, 2, 3... counting identical listings, so the saver can save each copy once."""
        if not rows or len(lay['cols']) != 1:
            return None
        h, top = lay['h'], lay['top']
        p = self._bar(img, lay)
        travel = (self.free - 2 * self.margin) if p is not None else 0
        f = min(1.0, max(0.0, p / travel)) if p and travel > 0 else 0.0
        view = {}
        for r in rows:
            text = (r['item'], r['each'], bool(r.get('sold')))
            view[round((r['y'] - top) / h)] = (text, _icon(img, r['x'], r['y'], h), r)
        self.views.append((f, view))
        if p is not None:
            self.last_seen = p
        self.rows_n = self._solve()
        slots, _ = self._layout(self.rows_n)
        out, seen = [], {}
        for s in sorted(slots):
            text, _, r = slots[s]
            seen[text] = seen.get(text, 0) + 1
            out.append(dict(r, copy=seen[text], slot=s))
        return out
