"""Copy the market page from MapleReader to the group server, so both serve the same page.

The page's one true copy is MapleReader/shopreader/market.html. Run after changing it:
    python tools/sync_market.py
"""
import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'MapleReader', 'shopreader', 'market.html')
DST = os.path.join(ROOT, 'maple-server', 'market.html')

if __name__ == '__main__':
    if '--check' in sys.argv:
        same = filecmp.cmp(SRC, DST, shallow=False)
        print('market.html copies match' if same else 'market.html copies DIFFER: run python tools/sync_market.py')
        sys.exit(0 if same else 1)
    shutil.copyfile(SRC, DST)
    print('copied', SRC, '->', DST)
