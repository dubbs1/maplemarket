"""Item pictures: each listing's icon is cut out of the shop window and kept in scans/icons.

One picture per item name. A picture from a normal row replaces one from a faded (sold) row, because
faded icons are washed out. The page shows them next to the item.
"""
import json
import os
import re
import threading

ICON_DIR = os.path.join('scans', 'icons')
_lock = threading.Lock()
_index = None                       # slug -> 'normal' | 'faded'


def slug(name):
    """'Cape LUK Scroll: Interme' -> 'cape-luk-scroll-interme' (same rule as the page uses)."""
    return re.sub(r'[^a-z0-9]+', '-', str(name).lower()).strip('-')[:80] or 'item'


def _load():
    global _index
    if _index is None:
        try:
            with open(os.path.join(ICON_DIR, 'index.json'), encoding='utf-8') as f:
                _index = json.load(f)
        except (OSError, ValueError):
            _index = {}
    return _index


def known():
    """Slugs that have a picture."""
    with _lock:
        return sorted(_load())


def keep(img, rows, h):
    """Cut the icon of each row (rows straight from parse_frame, with x/y on this screenshot)."""
    with _lock:
        idx, changed = _load(), False
        for r in rows:
            if 'x' not in r or 'y' not in r:
                continue
            s, kind = slug(r['item']), 'faded' if r.get('sold') else 'normal'
            if idx.get(s) == 'normal' or (idx.get(s) == 'faded' and kind == 'faded'):
                continue                             # already have a picture at least as good
            x, y = r['x'], r['y']
            box = (int(x - 1.15 * h) + 2, int(y - 0.52 * h) + 2, int(x - 0.1 * h) - 2, int(y + 0.42 * h) - 2)
            if box[0] < 0 or box[1] < 0 or box[2] > img.width or box[3] > img.height or box[2] - box[0] < 12:
                continue
            os.makedirs(ICON_DIR, exist_ok=True)
            img.crop(box).save(os.path.join(ICON_DIR, s + '.png'))
            idx[s], changed = kind, True
        if changed:
            path = os.path.join(ICON_DIR, 'index.json')
            with open(path + '.tmp', 'w', encoding='utf-8') as f:
                json.dump(idx, f)
            os.replace(path + '.tmp', path)          # all at once: a crash can't leave half a file


def reset_cache():
    """For tests: forget what was loaded (a different scans folder)."""
    global _index
    with _lock:
        _index = None
