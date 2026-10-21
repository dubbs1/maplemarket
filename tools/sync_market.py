"""Copy the market page from MapleReader to the group market, so every copy serves the same page.

The page's one true copy is MapleReader/shopreader/market.html. Run after changing it:
    python tools/sync_market.py
It goes to maple-cloud/public/index.html (the Vercel site, a plain file: marked as the group's page here).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'MapleReader', 'shopreader', 'market.html')
CLOUD = os.path.join(ROOT, 'maple-cloud', 'public', 'index.html')
MARK = '<script>window.MAPLE={mode:"shared"};</script><script>'   # (tells the page it is the group's)


def cloud_page():
    with open(SRC, encoding='utf-8') as f:
        return f.read().replace('<script>', MARK, 1)


if __name__ == '__main__':
    if '--check' in sys.argv:
        try:
            with open(CLOUD, encoding='utf-8') as f:
                cloud_same = f.read() == cloud_page()
        except OSError:
            cloud_same = False
        same = cloud_same
        print('market.html copies match' if same else 'market.html copies DIFFER: run python tools/sync_market.py')
        sys.exit(0 if same else 1)
    os.makedirs(os.path.dirname(CLOUD), exist_ok=True)
    with open(CLOUD, 'w', encoding='utf-8', newline='') as f:
        f.write(cloud_page())
    print('copied', SRC, '->', CLOUD)
