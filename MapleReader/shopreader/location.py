"""Where you are: the room (read off the minimap) and the channel (read off the Change Channel window)."""
import os
import re
import time
from PIL import Image, ImageOps
from .config import BUTTON_GREY, ROOM_MISSES, ROOM_REREAD, ROOM_SEARCH, ROOM_SLOW_SEARCH
from .layout import color_boxes
from .ocr import ocr_lines
from . import engine


MARKET = re.compile(r'(?:ket|ark|mar|war|wak)\w*\s*[<(\[{]\s*(\d{1,2})\s*[>)\]}]', re.I)


def _room_in(img, box, thorough=True):
    """Read "Free Market <N>" inside a small box. The minimap font is hard to read, so try a few ways."""
    c = img.crop(box).split()[0]                          # red channel: white text stands out best
    for sc, inv in ((3, False), (4, True), (2, False), (4, False))[:4 if thorough else 1]:
        g = ImageOps.autocontrast(c).resize((c.width * sc, c.height * sc), Image.LANCZOS)
        if inv:
            g = ImageOps.invert(g)
        m = MARKET.search(engine.text(ImageOps.expand(g, border=10, fill=255 if inv else 0), config='--psm 6'))
        if m and 1 <= int(m.group(1)) <= 30:
            return int(m.group(1))
    return None


def world_button_boxes(img):
    """Find the minimap's orange WORLD button (it has a blue button just left of it) in the top half
    of the screen, and return the box where "Free Market <N>" sits below it. Colour only, fast."""
    step = 2
    W, H = img.width // step, img.height // 2 // step
    sm = img.crop((0, 0, img.width, img.height // 2)).resize((W, H), Image.NEAREST)
    px = sm.load()
    orange = lambda p: p[0] > 200 and 130 < p[1] < 185 and p[2] < 70
    blue = lambda p: p[2] > 190 and 130 < p[1] < 195 and p[0] < 90
    runs = []                                        # horizontal runs of orange pixels
    for y in range(H):
        x = 0
        while x < W:
            if orange(px[x, y]):
                x0 = x
                while x < W and orange(px[x, y]):
                    x += 1
                if x - x0 >= 2:
                    runs.append([y, x0, x])
            x += 1
    groups = []                                      # join runs that touch the run above into shapes
    for r in runs:
        for g in groups:
            if g[3] in (r[0] - 1, r[0] - 2) and r[1] < g[2] + 2 and r[2] > g[1] - 2:
                g[1], g[2], g[3] = min(g[1], r[1]), max(g[2], r[2]), r[0]
                g[4] += 1
                break
        else:
            groups.append([r[0], r[1], r[2], r[0], 1])   # y0, x0, x1, y1, number of runs
    out = []
    for y0, x0, x1, y1, n in groups:
        hb = y1 - y0 + 1
        if not (4 <= hb <= 20 and 2.2 * hb <= x1 - x0 <= 6 * hb and n >= hb * 0.6):
            continue                                 # not shaped like the WORLD button
        if not any(blue(px[x, yy]) for yy in range(y0, y1 + 1) for x in range(max(0, x0 - 4 * hb), x0)):
            continue                                 # the blue -/+ buttons sit just left of WORLD
        bx0, by0, bx1 = x0 * step, y0 * step, x1 * step
        hb *= step
        for l, t, r, b in ((8.5, 2.5, 1, 5.6), (7, 3.2, 0.6, 5.0), (7.5, 3.0, 0.5, 5.4), (9, 2.2, 1, 5.8)):
            out.append((max(0, int(bx0 - l * hb)), by0 + int(t * hb), min(img.width, int(bx1 + r * hb)), by0 + int(b * hb)))
            # the reading is picky about framing, so offer a few frames around the "Free Market <N>" line
    return out


def minimap_boxes(img, lines=None):
    """Where the minimap's room text could be: the screen's top-left corner, plus under any
    "MINI MAP" / "Hidden Street" label found by a quick pass."""
    W, H = img.width, img.height                     # top-left corner: a few sizes, since the reading is picky about framing
    boxes = [(0, 0, min(W, 300), min(H, 120)), (0, 0, W // 6, H // 8), (0, 0, W // 8, H // 11), (0, 0, min(W, 240), min(H, 110))]
    if lines is None:
        lines = ocr_lines(img.crop((0, 0, img.width, int(img.height * 0.6))), scale=1)
    for l in lines:
        if re.search(r'mark|arke', l['text'], re.I):     # the "Free Market <N>" line itself
            box = (max(0, l['x0'] - 110), max(0, l['y0'] - 20), min(img.width, l['x1'] + 90), min(img.height, l['y1'] + 20))
            if box not in boxes:
                boxes.insert(0, box)
        if re.search(r'min[it]\s*ma|mun|hidd|stre|sire', l['text'], re.I):
            tight = (l['x0'] + 40, l['y0'] + 35, min(img.width, l['x0'] + 240), min(img.height, l['y0'] + 85))
            if re.search(r'min', l['text'], re.I) and tight not in boxes:
                boxes.append(tight)                      # just the "Free Market <N>" line under the MINI MAP label
            box = (max(0, l['x0'] - 10), max(0, l['y0'] - 4), min(img.width, l['x0'] + 260), min(img.height, l['y0'] + 90))
            if box not in boxes:
                boxes.append(box)
    return boxes


class RoomWatcher:
    """Remembers where the minimap is and re-reads that small spot every few seconds."""
    def __init__(self, keep_picture=True):
        self.room, self.box, self.last_read, self.last_search = None, None, 0, 0
        self.misses, self.last_slow = 0, 0
        self.saved = not keep_picture              # True = don't write scans/room_check.png

    def update(self, img, lines=None, force=False):
        now = time.time()
        if self.box and (force or now - self.last_read > ROOM_REREAD):   # rooms only change through a portal
            self.last_read = now
            r = _room_in(img, self.box)
            if r:
                self.room = r
            else:
                self.misses += 1
                if self.misses >= ROOM_MISSES:                       # minimap really gone/moved: search again
                    self.box, self.misses = None, 0
                return self.room                           # one failed read: keep the room we know
            self.misses = 0
        if not self.box and (force or now - self.last_search > ROOM_SEARCH):
            self.last_search = now
            if now - self.last_slow > ROOM_SLOW_SEARCH:  # backup: read the top-left of the screen to find the minimap
                self.last_slow = now
                W, H = img.width, img.height
                lines = (lines or []) + ocr_lines(img.crop((0, 0, W // 2, H // 3)), scale=1)
            corners = 4                                    # the first boxes are the screen corner: one quick try each
            cands = minimap_boxes(img, lines or [])
            cands = cands[:corners] + world_button_boxes(img) + cands[corners:]
            for i, box in enumerate(cands):
                r = _room_in(img, box, thorough=i >= corners)
                if r:
                    self.room, self.box, self.last_read = r, box, now
                    break
        if not self.box and not self.saved and os.path.isdir('scans'):
            self.saved = True                          # keep one picture of the top-left corner, for fixing
            img.crop((0, 0, img.width // 3, img.height // 4)).save(os.path.join('scans', 'room_check.png'))
        return self.room


def channel_window(img):
    """Where the Change Channel window's grid of grey buttons is, or None. Fast (colour only)."""
    for b in color_boxes(img, BUTTON_GREY, minc=6, vgap=2):
        if b[2] - b[0] > 3 * (b[3] - b[1]):        # a wide grid, not some other grey patch
            return b
    return None


def read_channel(img, lines=None):
    """If the Change Channel window is open, read the highlighted (blue) channel button."""
    g = channel_window(img)
    if not g:
        return None
    hh = max(8, (g[3] - g[1]) // 9)
    box = (max(0, g[0] - 2 * hh), max(0, g[1] - 2 * hh), min(img.width, g[2] + 2 * hh), min(img.height, g[3] + 2 * hh))
    c = img.crop(box)
    px, W, H = c.load(), c.width, c.height
    blue = lambda p: p[2] > 190 and p[0] < 110 and 120 < p[1] < 210

    def runs(cnt, minv):
        out, st = [], None
        for i, v in enumerate(cnt + [0]):
            if v >= minv and st is None:
                st = i
            if v < minv and st is not None:
                out.append((st, i)); st = None
        return out
    votes = {}
    # every blue patch: the highlighted channel button, but also the blue "CHANGE CHANNEL" button,
    # so try each patch and keep the one that reads as "CH.<number>"
    for ry in runs([sum(blue(px[i, j]) for i in range(0, W, 2)) for j in range(H)], 6):
        if not 6 <= ry[1] - ry[0] <= 3 * hh:
            continue
        for rx in runs([sum(blue(px[i, j]) for j in range(ry[0], ry[1])) for i in range(W)], max(3, (ry[1] - ry[0]) // 2)):
            if rx[1] - rx[0] < 3 * hh:
                continue
            btn = c.crop((rx[0], ry[0], rx[1], ry[1]))
            got = {}
            for sc, thr in ((3, 170), (3, 180), (3, 190), (4, 170), (4, 180)):
                g = ImageOps.grayscale(btn).resize((btn.width * sc, btn.height * sc), Image.LANCZOS).point(lambda v, t=thr: 0 if v > t else 255)
                txt = engine.text(ImageOps.expand(g, border=10, fill=255), config='--psm 7 -c tessedit_char_whitelist=CH.0123456789')
                m = re.search(r'CH\.?(\d{1,2})', txt)
                if m and 1 <= int(m.group(1)) <= 40:
                    got[int(m.group(1))] = got.get(int(m.group(1)), 0) + 1
            if got and max(got.values()) >= 3:
                votes = got
                break
        if votes:
            break
    best = max(votes.items(), key=lambda kv: kv[1], default=(None, 0))
    return best[0] if best[1] >= 3 else None
