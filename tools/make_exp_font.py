"""Builds MapleReader/shopreader/exp_font.py: the shapes of the status bar's characters, cut from test screenshots
whose text is known. The EXP tracker reads digits by comparing them with these shapes (more reliable than a
general text reader on this small pixel font).

    python tools/make_exp_font.py

To add digits (say, a screenshot showing a 5): add the picture to MapleReader/tests/fixtures and a line to SOURCES
below with the text each part shows, then run this again.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'MapleReader'))
from PIL import Image                                            # noqa: E402
from shopreader import exp as E                                  # noqa: E402

# picture, then for each text on its status bar: (which part, the characters it shows, left to right)
BAR = [('hp', '1303/1303'), ('mp', '1072/1072'), ('exp', '93,499'), ('pct', '43.17%'), ('level', '37')]
SOURCES = [
    ('live_shop.png', [('mp', '1068/1072')] + BAR[:1] + BAR[2:]),
    ('desk_live.png', BAR), ('s711.png', BAR),
]
# A digit no picture shows yet, drawn by hand from the others' strokes (the top of 7, the left of 6, the bottom of
# 3). Used only until a real one is cut from a picture.
MADE_UP = {
    ('small', '5'): ('65555553', '86444441', '82000000', '82000000', '87777500', '00333363',
                     '00000074', '00000074', '61000074', '43222241', '04999700'),
}

# Only pictures at the usual interface size: a shape cut from a resized one is blurred and matches too much.
# (ch2.png, live_ch.png and shopS.png, at other sizes, test the reading instead: tests/test_exp.py.)


def main():
    found = {}
    for name, parts in SOURCES:
        img = Image.open(os.path.join(ROOT, 'MapleReader', 'tests', 'fixtures', name)).convert('RGB')
        bar = E.find_bar(img)
        if not bar:
            sys.exit(f'{name}: no status bar found')
        if abs(bar['size'] - 1) > 0.03:
            sys.exit(f'{name}: not at the usual interface size ({bar["size"]:.2f})')
        for part, text in parts:
            glyphs = E.glyphs_of(img, bar, part)
            if len(glyphs) != len(text):
                sys.exit(f'{name} {part}: found {len(glyphs)} characters, expected {len(text)} ({text})')
            for ch, g in zip(text, glyphs):
                samples = found.setdefault((E.FONT_OF[part], ch), [])
                if g not in samples:
                    samples.append(g)
    for key, g in MADE_UP.items():
        if key not in found:
            found[key] = [list(g)]
    out = ['"""The status bar\'s digit shapes (made by tools/make_exp_font.py; don\'t edit by hand).', '',
           'GLYPHS[font][character] = list of samples; each sample is rows of shades, "0" (background) to "9" (ink)."""', '',
           'GLYPHS = {']
    for font in sorted({f for f, _ in found}):
        out.append(f'    {font!r}: {{')
        for (f, ch), samples in sorted(found.items()):
            if f == font:
                out.append(f'        {ch!r}: [')
                for g in samples:
                    out.append('            (' + ', '.join(repr(r) for r in g) + '),')
                out.append('        ],')
        out.append('    },')
    out.append('}')
    path = os.path.join(ROOT, 'MapleReader', 'shopreader', 'exp_font.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    have = {f: ''.join(sorted(ch for ff, ch in found if ff == f)) for f in {f for f, _ in found}}
    print('wrote', path, 'digits:', have)


if __name__ == '__main__':
    main()
