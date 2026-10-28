"""Finding areas of one UI colour on a screenshot, fast (Pillow does the pixel work: no text reading)."""
from PIL import Image, ImageChops

_SMALL = [None]                                    # (image, its small copy): one pair, swapped whole (two threads use it)


def _small(img, step):
    """The screenshot shrunk by `step`, made once per screenshot (several colour checks look at it)."""
    pair = _SMALL[0]
    if pair and pair[0] is img:
        return pair[1]
    sm = img.resize((max(1, img.width // step), max(1, img.height // step)), Image.NEAREST)
    _SMALL[0] = (img, sm)
    return sm


def color_boxes(img, col, tol=6, cell=24, minc=8, vgap=8):
    """Find areas of the screen filled with one UI colour. Returns boxes (x0, y0, x1, y1), biggest first."""
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
    steps = [(1, 0), (-1, 0)] + [(0, d) for d in range(-vgap, vgap + 1) if d]
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
