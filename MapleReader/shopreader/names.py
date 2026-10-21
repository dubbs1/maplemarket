"""Item names: cleaning up common OCR mistakes, and snapping onto items.txt if you made one."""
import difflib
import os
import re
from .config import NAME_MATCH


def load_items(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8-sig') as f:     # -sig: Notepad's invisible first character
        return [ln.split('|')[0].strip() for ln in f if ln.strip() and not ln.startswith('#')]


def real_name(nm):
    words = re.findall(r'[A-Za-z]+', nm)
    return sum(map(len, words)) >= 5 and (any(len(w) >= 4 for w in words) or sum(len(w) >= 3 for w in words) >= 2)


def fix_w(text):
    """A capital W read as two or three marks at the start of a word (also after a hyphen): "Vvhite", "Yvhite",
    "Ywhite", "VVand", "yyatch", "Y¥atch", "¥¥atch", "Ink-and-vVYash", "-WYash", "-v¥Vash" -> "White", "Wand",
    "Watch", "Ink-and-Wash". No word starts with these, a real W followed by a small letter ("Wyvern") is kept,
    and a single V or Y ("Vest", "Yeti") is left alone. The market page has the same rule (fixName), for old scans."""
    return re.sub(r'(?<![A-Za-z0-9])(?!W[a-z])(?:[VvWwYy¥]{2}[VWY¥]|[VvWwYy¥]{2}|\\/\\/)(?=[a-z])', 'W', text)


def fix_name(name, items):
    """Clean up common OCR mistakes in an item name."""
    name = re.sub(r'^[^A-Za-z0-9]+', '', fix_w(name))  # stray symbols in front, e.g. "#Wand" (a W read as "¥¥" fixed first)
    name = re.sub(r'\bl(?=[a-z])', 'I', name)          # OCR reads a capital I as l: "lron" -> "Iron"
    name = fix_w(name).replace('VV', 'W').replace('Scrolk', 'Scroll').replace('Scro11', 'Scroll')
    name = re.sub(r'\b[BH]i[uU]e\b|\bbIUe\b', 'Blue', name)   # the l of "Blue" read as i ("Biue", "Hiue", "bIUe")
    name = re.sub(r'\bV[Ww]?(?=h)', 'W', name)          # W read as V: "Vhite"/"VWhite"/"Vwhite" -> "White"
    name = re.sub(r'\bVand\b', 'Wand', name)
    name = re.sub(r'\b[YV]W', 'W', name)                 # "Ice YWand" -> "Ice Wand"
    name = re.sub(r'\b[YV][YV](?=[a-z])', 'W', name)     # "Ice YYand" / "VVand" -> "Ice Wand"
    small = {'of', 'for', 'the', 'a', 'an', 'and', 'to', 'in', 'on', 'with'}
    name = ' '.join(w[:1].upper() + w[1:] if w.islower() and (i == 0 or w not in small) else w
                    for i, w in enumerate(name.split()))   # "Smithing kit" -> "Smithing Kit", so one item = one name
    # snap a slightly misread name onto the closest known item (only if you made items.txt)
    if not items or name in items:
        return name
    m = difflib.get_close_matches(name, items, n=1, cutoff=NAME_MATCH)
    return m[0] if m else name
