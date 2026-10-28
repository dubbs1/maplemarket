"""Where you are, for the EXP log: the map's name (the minimap's title) and the party (its window's HP bars)."""
import re
from PIL import Image, ImageChops, ImageOps
from . import engine


def world_buttons(img):
    """Find the minimap's orange WORLD button (it has a blue button just left of it) in the top half
    of the screen: (x0, y0, x1, height) in screen pixels. Colour only, fast."""
    step = 2
    W, H = img.width // step, img.height // 2 // step
    sm = img.crop((0, 0, img.width, img.height // 2)).resize((W, H), Image.NEAREST)
    px = sm.load()
    blue = lambda p: p[2] > 190 and 130 < p[1] < 195 and p[0] < 90
    r, g, b = sm.split()[:3]                         # the orange pixels, found in Pillow (pixel by pixel took ~50 ms)
    orange = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v > 200 else 0), g.point(lambda v: 255 if 130 < v < 185 else 0)),
                                 b.point(lambda v: 255 if v < 70 else 0)).tobytes()
    runs = []                                        # horizontal runs of orange pixels
    for y in range(H):
        for m in re.finditer(rb'\xff{2,}', orange[y * W:(y + 1) * W]):
            runs.append([y, m.start(), m.end()])
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
        out.append((x0 * step, y0 * step, x1 * step, hb * step))
    return out


# ---------- the map's name (the minimap's title) and the party (its window's HP bars), for the EXP log ----------
# the minimap title's FIRST line (the area: never a map's name). When the second line can't be read, the first
# must not become the EXP log's map ("Dungeon" for The Cave of Evil Eye)
REGIONS = {'victoria road', 'dungeon', 'hidden street', 'ossyria', 'maple island', 'el nath mts', 'el nath mts.', 'orbis',
           'ludus lake', 'ludibrium', 'aqua road', 'minar forest', 'leafre', 'mu lung', 'herb town', 'nihal desert', 'ariant',
           'magatia', 'ellin forest', 'masteria', 'zipangu', 'mushroom shrine', 'florina beach', 'world tour', 'omega sector',
           'korean folk town', 'temple of time', 'singapore', 'malaysia', 'thailand', 'china', 'taiwan', 'nautilus', 'ereve', 'rien'}


def _map_fix(line):
    words = re.sub(r'(^|[\s<(])[iIl|]st\b', r'\g<1>1st', line).split()
    while words and not re.match(r'([A-Z0-9][A-Za-z0-9\'-]+|<\d)', words[0]):   # bits of the map's picture read as text
        words.pop(0)
    line = ' '.join(words)
    line = re.sub(r'(^|[\s<(])[iIl|]st\b', r'\g<1>1st', line.strip(' .,:;|!_-'))   # "ist Stage" -> "1st Stage"
    line = re.sub(r'\s+', ' ', line).replace('“', '<').replace('”', '>')
    fm = re.search(r'Free Market <\d{1,2}>', line)
    if fm:
        return fm.group(0)                           # (the market's own name, without stray bits in front)
    line = re.sub(r'\b[iIl|1]{1,4}$', lambda m: 'I' * len(m.group(0)), line)   # "Evil Eye ill" -> "Evil Eye III"
    if line.lower().rstrip('.') in REGIONS:
        return None
    return line if len(re.findall(r'[A-Za-z]', line)) >= 4 and re.search(r'[A-Za-z]{3,}', line) and not re.search(r'[?=|]', line) else None


MAP_READS = tuple((th, sc) for th in (185, 190, 195, 200) for sc in (2, 3, 4))   # 12 reads, ~0.5 s, every 20 s (EXP log)


def _room_no(line):
    """The room in a title line ("Free Market <2>", or "Market <2>" when the F was lost), for voting on the number."""
    m = re.search(r'arket <(\d{1,2})>', line)
    return m.group(1) if m else None


def read_map(img, reads=MAP_READS, need=3, key=None):
    """The map's name from the minimap's title ("Hidden Street" / "1st Accompaniment <1st Stage>": the second line
    is the map), or None. White letters on light blue: only the near-white ones are kept, read a few ways (`reads`:
    (threshold, scale) pairs), and the reading at least `need` of them agree on wins. `key` turns a read line into
    what is voted on (the line itself without it; None = no vote)."""
    for bx0, by0, bx1, hb in world_buttons(img):
        box = (max(0, int(bx0 - 18 * hb)), by0 + int(2 * hb), min(img.width, int(bx1 + 0.8 * hb)), by0 + int(5.9 * hb))
        red = img.crop(box).split()[0]
        votes = {}
        for th, sc in reads:
            g = red.point(lambda v, th=th: 0 if v > th else 255).resize((red.width * sc, red.height * sc), Image.LANCZOS)
            lines = [_map_fix(x) for x in engine.text(ImageOps.expand(g, border=12, fill=255), config='--psm 6').splitlines()]
            lines = [x for x in lines if x]
            k = (key(lines[-1]) if key else lines[-1]) if lines else None
            if k:
                votes[k] = votes.get(k, 0) + 1
        best = max(votes, key=lambda k: (votes[k], len(k))) if votes else None
        if best and votes[best] >= need:                 # a real name reads the same again and again; junk doesn't
            return best
    return None


def party_size(img):
    """How many are in your party: the party window's HP bars (bottom right), stacked one under the other,
    starting at the same left edge. None when there's no party window (solo, or it's closed). Colour only."""
    W, H = img.width, img.height
    x0, y0 = int(W * 0.55), int(H * 0.55)
    reg = img.crop((x0, y0, W, H))
    r, g, b = reg.split()[:3]
    mask = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v > 170 else 0), g.point(lambda v: 255 if v < 60 else 0)),
                               b.point(lambda v: 255 if v < 60 else 0))
    bands, live = [], []                             # stretches of red, joined row to row: one per bar
    for y in range(mask.height):
        row = mask.crop((0, y, mask.width, y + 1)).tobytes()
        nxt = []
        for m in re.finditer(rb'\xff{8,}', row):
            for band in live:
                if abs(band[2] - m.start()) <= 6:
                    band[1], band[3] = y, max(band[3], m.end() - m.start())
                    nxt.append(band)
                    break
            else:
                band = [y, y, m.start(), m.end() - m.start()]
                bands.append(band)
                nxt.append(band)
        live = nxt
    bars = [(a, x, z - a, w) for a, z, x, w in bands if 3 <= z - a + 1 <= 16]
    best = None
    for _, x, h, _ in bars:                          # bars sharing a left edge and height, evenly spaced: the party window
        same = [(a, w) for a, xx, hh, w in bars if abs(xx - x) <= 6 and abs(hh - h) <= 4]
        col = sorted({a for a, _ in same})
        gaps = [q - p for p, q in zip(col, col[1:])]
        if max(w for _, w in same) < W * 0.026:     # (red skill icons stack up too, but none is a long bar)
            continue
        if len(col) >= 2 and 14 <= min(gaps) <= 60 and all(abs(gp / min(gaps) - round(gp / min(gaps))) < 0.15 for gp in gaps):
            n = round((col[-1] - col[0]) / min(gaps)) + 1   # (a member at 0 HP has no red: still counted)
            best = max(best or 0, n)
    return best if best and best <= 6 else None
