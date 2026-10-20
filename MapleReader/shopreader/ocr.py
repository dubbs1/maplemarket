"""Tesseract: finding it, and reading a picture into lines of text with their positions."""
import os
import re
import shutil
import pytesseract
from PIL import Image, ImageOps
from .config import CFG, SCALE, TESS_PATHS
from . import engine


def find_tesseract():
    """The current Windows installer no longer adds Tesseract to PATH, so look in the usual folders."""
    if shutil.which('tesseract'):
        return True
    for p in TESS_PATHS:
        if os.path.isfile(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return False


def to_number(t):
    return int(re.sub(r'[^\d]', '', t) or 0)


def ocr_lines(img, red=False, ox=0, oy=0, scale=SCALE):
    """OCR an image and return text lines with boxes in screen coordinates."""
    big = img.resize((img.width * scale, img.height * scale), Image.LANCZOS) if scale > 1 else img
    g = ImageOps.autocontrast(big.split()[0] if red else ImageOps.grayscale(big))
    g = ImageOps.expand(g, border=10, fill=255)
    d = engine.data(g, config='--psm 11 ' + CFG)
    words = {}
    for i, t in enumerate(d['text']):
        if not t.strip() or float(d['conf'][i]) < 20:
            continue
        words.setdefault((d['block_num'][i], d['par_num'][i], d['line_num'][i]), []).append(i)
    out = []
    for idx in words.values():
        idx.sort(key=lambda k: d['left'][k])
        x0 = (min(d['left'][i] for i in idx) - 10) // scale + ox
        y0 = (min(d['top'][i] for i in idx) - 10) // scale + oy
        x1 = (max(d['left'][i] + d['width'][i] for i in idx) - 10) // scale + ox
        y1 = (max(d['top'][i] + d['height'][i] for i in idx) - 10) // scale + oy
        out.append(dict(text=' '.join(d['text'][i] for i in idx), x0=x0, y0=y0, x1=x1, y1=y1, red=red))
    return out


def pitch(pr, default=56):
    """Height of one shop row in pixels (about 56 at normal size). Everything else scales from it."""
    gaps = []
    for c in {l['x0'] // 30 for l in pr}:            # per list column
        ys = sorted(l['y0'] for l in pr if abs(l['x0'] // 30 - c) <= 1)
        gaps += [b - a for a, b in zip(ys, ys[1:]) if 25 < b - a < 260]
    if not gaps:
        return default
    g = min(gaps)                                    # smallest gap = one row (sold or missed rows make bigger gaps)
    close = [x for x in gaps if x < 1.25 * g]
    return sorted(close)[len(close) // 2]
