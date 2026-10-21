"""Checks item-name fixes: one item, one name.

1. A W read as two or three marks at a word's start, after a space or a hyphen ("Ink-and-vVYash", "-¥Wash",
   "-WYash", "-v¥Vash") becomes W; real words ("Wyvern", "Vest", "Yeti") stay as they are.
2. The market page fixes names the same way (fixName in market.html, for old scans): checked with node, if it's here.
"""
import json
import os
import shutil
import subprocess
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from shopreader.names import fix_name, fix_w                # noqa: E402

fails = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        fails.append(what)


CASES = {
    'Ink-and-Wash Painting': 'Ink-and-Wash Painting', 'Ink-and-vVYash Painting': 'Ink-and-Wash Painting',
    'Ink-and-¥Wash Thought': 'Ink-and-Wash Thought', 'Ink-and-¥Vash Thought': 'Ink-and-Wash Thought',
    'Ink-and-WYash Painting': 'Ink-and-Wash Painting', 'Ink-and-v¥Vash Thought': 'Ink-and-Wash Thought',
    'Vvhite Gown': 'White Gown', 'Yvhite Gown': 'White Gown', 'Ice YYand': 'Ice Wand', 'yyatch': 'Watch', '¥¥atch': 'Watch',
    'Wyvern Scale': 'Wyvern Scale', 'Vvyvern Scale': 'Wyvern Scale', 'Vest': 'Vest', 'Yeti Horn': 'Yeti Horn',
    'Biue Lutia': 'Blue Lutia', 'smithing kit': 'Smithing Kit', 'lron Axe': 'Iron Axe', 'Scroll for Gloves for ATT 60%': 'Scroll for Gloves for ATT 60%',
}

if __name__ == '__main__':
    print('Item names:')
    for raw, want in CASES.items():
        got = fix_name(raw, [])
        check(got == want, f'{raw!r} -> {got!r}')
    check(fix_w('Ink-and-vVYash') == 'Ink-and-Wash' and fix_w('Wash') == 'Wash', 'fix_w on its own (also used for shop names)')
    node = shutil.which('node') if os.name != 'nt' else None   # (Linux checks; Windows' command line mangles ¥)
    if node:
        page = open(os.path.join(os.path.dirname(HERE), 'shopreader', 'market.html'), encoding='utf-8').read()
        src = page[page.index('const fixW = s =>'):page.index('// Items saved before a fix')]
        js = src + '\nconst all = ' + json.dumps(list(CASES)) + ';\nconsole.log(JSON.stringify(all.map(fixName)));'
        out = subprocess.run([node, '-e', js], capture_output=True, text=True, encoding='utf-8')
        got = json.loads(out.stdout or 'null')
        same = got == [fix_name(x, []) for x in CASES]
        check(same, 'the market page fixes names the same way' + ('' if same else f': {out.stderr or got}'))
    else:
        print('  (node is not here: the market page\'s copy of the rules is checked by the page checks instead)')
    print()
    print('NAMES CHECK PASSED' if not fails else f'NAMES CHECK: {len(fails)} FAILED')
    sys.exit(1 if fails else 0)
