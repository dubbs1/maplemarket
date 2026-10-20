"""The program itself: reads one picture (--image), or watches the screen and saves listings."""
import argparse
import os
import sys
import threading
from PIL import Image
from .config import INTERVAL, VOLUME
from .location import RoomWatcher, read_channel
from .names import load_items
from .ocr import find_tesseract
from .rows import fmt, parse_frame
from .scanner import ALL_SCANS, Scanner
from . import engine, __version__


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description='Reads Free Market shop windows off your screen.')
    ap.add_argument('--image', help='read one screenshot file instead of watching the screen (for testing)')
    ap.add_argument('--channel', type=int, default=0, help='channel you start in (you can change it while running)')
    ap.add_argument('--interval', type=float, default=INTERVAL, help='seconds between looks')
    ap.add_argument('--monitor', type=int, default=1, help='1 = main monitor, 2 = second monitor')
    ap.add_argument('--items', default='items.txt', help='optional list of item names, one per line')
    ap.add_argument('--quiet', action='store_true', help='no chime when listings are saved')
    ap.add_argument('--volume', type=float, default=VOLUME, help='chime loudness, 0.03 (very soft) to 1.0')
    ap.add_argument('--slow-ocr', action='store_true', help='use the old, slower way of running Tesseract')
    return ap.parse_args(argv)


def read_picture(path, items, channel=0):
    """--image mode: print what one screenshot shows. Uses the same room search as live mode."""
    im = Image.open(path).convert('RGB')
    rows, _, _ = parse_frame(im, items)
    room = RoomWatcher(keep_picture=False).update(im, [], force=True)
    if not rows:
        print('channel window shows:', read_channel(im))
    print('room:', room)
    for r in rows:
        print(fmt(r, room or 0, channel))


def listen_for_typing(scanner):
    """Lets you type a channel ('3') or a room ('room 9') into the black window."""
    state = scanner.state

    def ask():
        for line in sys.stdin:
            t = line.strip().lower()
            c = t.replace('ch', '').strip()
            if t.startswith('room') and t[4:].strip().isdigit() and int(t[4:]) <= 40:
                scanner.set_room(int(t[4:]))
                print('  room set to', state['room'])
            elif c.isdigit() and 1 <= int(c) <= 40:
                scanner.set_channel(int(c))
                print('  channel set to', state['ch'])
            elif t:
                print('  Type a channel number like 3, or "room 9" if the room is not read.')
    threading.Thread(target=ask, daemon=True).start()


def watch(a, items):
    scanner = Scanner(items, a.channel, a.interval, a.monitor, a.volume, a.quiet)
    listen_for_typing(scanner)
    print('Watching your screen. Close this window or press Ctrl+C to stop.')
    print('Saving to', os.path.abspath(scanner.out))
    print('  and to', os.path.abspath(ALL_SCANS), '(import this one on the site: only new rows are added)')
    if not scanner.state['ch']:
        print('Open the Change Channel window once so I can read your channel, or type it here (1-40) and press Enter.')
    print('Looking for a shop window...')
    scanner.run()


def main(argv=None):
    a = parse_args(argv)
    if not find_tesseract():
        print('Tesseract was not found. Install it from the UB-Mannheim page (default folder),')
        print(r'or edit TESS_PATHS in shopreader\config.py to point at tesseract.exe.')
        input('Press Enter to close.')
        return
    if a.slow_ocr:
        engine.use('slow')
    if not a.image:
        how = 'fast (Tesseract kept in memory)' if engine.mode() == 'fast' else 'standard (tesseract.exe each time)'
        print(f'MapleReader {__version__}. Text reading: {how}.')
    items = load_items(a.items)
    if a.image:
        read_picture(a.image, items, a.channel)
    else:
        watch(a, items)
