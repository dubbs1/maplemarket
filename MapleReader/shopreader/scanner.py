"""The watching loop, shared by the black-window version (session.py) and the app window (app.py).

It takes screenshots, waits for a shop list to stop moving, reads it and saves new listings.
Everything it has to tell you goes through an Events object, so each front end can show it its own way.
"""
import os
import threading
import time
from datetime import datetime
from PIL import Image, ImageOps, ImageChops
from .config import CHANGED_LIST, CHANGED_SHOP, FORGET_AFTER, INTERVAL, PIXEL_CHANGE, THUMB, TITLE_TRIES, VOLUME
from .layout import list_boxes
from .location import RoomWatcher, channel_window, read_channel
from .rows import fmt, parse_frame
from .scroll import ScrollTracker
from .sound import beep
from . import icons

ALL_SCANS = os.path.join('scans', 'all_scans.txt')


class Events:
    """What the scanner reports. This default version prints to the black window."""
    def message(self, text):
        print(text)

    def status(self, what):
        """'looking' (no shop on screen), 'reading', 'waiting' (shop seen, channel unknown)."""

    def channel(self, ch, auto):
        if auto:
            print(f'  channel set to {ch} (read from the Change Channel window)')

    def room(self, room):
        """The room number read from the minimap changed."""

    def shop(self, name, rows_seen):
        """A shop is open: its name and how many of its rows have been seen so far."""

    def saved(self, rows, room, ch, total):
        warn = '' if room else '  (room not read: is the minimap open? or type "room 9")'
        print(f'Saved {len(rows)} from "{rows[0]["shop"]}" (room {room}, ch {ch}). Total {total}.{warn}')


def thumb(im):
    return ImageOps.grayscale(im.resize((THUMB, THUMB)))


def differs(t1, t2, whole):
    """Did the picture change? whole=True asks the stricter 'is this a different shop?'."""
    if t1 is None or t2 is None:
        return True
    n = ImageChops.difference(t1, t2).point(lambda v: 255 if v > PIXEL_CHANGE else 0).histogram()[255]
    return n > (CHANGED_SHOP if whole else CHANGED_LIST)


class Saver:
    """Writes new listings to the scan files, skipping ones already saved in the last 10 minutes."""
    def __init__(self, out, state, events, volume=VOLUME, quiet=False):
        self.out, self.state, self.events = out, state, events
        self.volume, self.quiet = volume, quiet
        self.logged, self.total, self.pending = {}, 0, []

    def save(self, rows, rm):
        now, new, seen_now = time.time(), [], {}
        for r in rows:
            base = (r['item'], r['each'], rm, self.state['ch'], bool(r.get('sold')))   # shop name left out: it can be misread differently
            if 'copy' in r:                                    # counted over the whole list (see scroll.py)
                n = r['copy']
            else:
                n = seen_now[base] = seen_now.get(base, 0) + 1   # two identical listings are two copies
            k = base + (n,)
            if now - self.logged.get(k, 0) > FORGET_AFTER:
                self.logged[k] = now
                new.append(dict(r, copy=n))
        if len(self.logged) > 20000:                  # a long session: forget listings older than 10 minutes
            self.logged = {k: t for k, t in self.logged.items() if now - t <= FORGET_AFTER}
        if not new:
            return
        when = datetime.now()
        text = ''.join(fmt(r, rm, self.state['ch'], when) + '\n' for r in new)
        for path in (self.out, ALL_SCANS):            # this session's file, and the one file that has everything
            with open(path, 'a', encoding='utf-8') as f:
                f.write(text)
        self.total += len(new)
        self.events.saved(new, rm, self.state['ch'], self.total)
        if not self.quiet:
            beep(self.volume)

    def flush(self):
        """Save shops seen before the channel was known."""
        for r_, rm_ in self.pending:
            self.save(r_, rm_)
        self.pending = []


class Scanner:
    """Watches the screen until stop() is called. Safe to run in a background thread."""
    def __init__(self, items=(), channel=0, interval=INTERVAL, monitor=1, volume=VOLUME, quiet=False, events=None):
        self.items, self.interval, self.monitor = list(items), interval, monitor
        self.events = events or Events()
        self.state = {'ch': channel if 1 <= channel <= 40 else 0, 'room': 0}
        os.makedirs('scans', exist_ok=True)
        self.out = os.path.join('scans', datetime.now().strftime('scan_%Y-%m-%d_%H%M.txt'))
        self.saver = Saver(self.out, self.state, self.events, volume, quiet)
        self._stop = threading.Event()

    # --- controls (from the window or the keyboard) ---
    def stop(self):
        self._stop.set()

    def set_channel(self, ch):
        if 1 <= ch <= 40:
            self.state['ch'] = ch
            self.saver.flush()

    def set_room(self, room):
        self.state['room'] = room

    def set_sound(self, volume=None, quiet=None):
        if volume is not None:
            self.saver.volume = volume
        if quiet is not None:
            self.saver.quiet = quiet

    # --- the loop ---
    def run(self):
        import mss
        ev, state, saver = self.events, self.state, self.saver
        nagged, region, status = 0, None, None
        prev_t = done_t = done_ch = None
        title_tries, last_room = 0, None
        watcher = RoomWatcher()
        tracker, shop_now = ScrollTracker(), None

        def set_status(s):
            nonlocal status
            if s != status:
                status = s
                ev.status(s)

        set_status('looking')
        with (getattr(mss, 'MSS', None) or mss.mss)() as sct:
            mon = sct.monitors[min(self.monitor, len(sct.monitors) - 1)]
            while not self._stop.is_set():
                time.sleep(self.interval)
                shot = sct.grab(mon)
                img = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
                boxes = list_boxes(img)              # is a shop list on screen? (colour check, instant)
                if not boxes:
                    prev_t = done_t = None
                    if shop_now is not None:         # shop closed: next one is a new visit
                        tracker.reset()
                        shop_now = None
                        ev.shop(None, 0)
                    set_status('looking')
                    g = channel_window(img)          # or the Change Channel window?
                    if g:
                        t = thumb(img.crop(g))
                        if differs(done_ch, t, False):
                            ch = read_channel(img)
                            if ch:
                                done_ch = t
                                if ch != state['ch']:
                                    state['ch'] = ch
                                    ev.channel(ch, True)
                                saver.flush()
                    continue
                b = boxes[0]
                edges = (b[0], b[2])                 # the list's left and right edges, as found by colour
                if region and region.get('edges') != edges:
                    # the list changed width or moved sideways: the game window was resized, the "UI Size" changed,
                    # or every visible row is now sold. The rows' size and places are different: measure again.
                    region, prev_t, done_t = None, None, None
                    tracker.reset()
                if region:                           # watch the scrollbar too: identical rows look unchanged
                    b = (b[0], b[1], min(img.width, int(b[2] + 0.65 * region['h'])), b[3])
                    tracker.observe(img, region)     # follow the scrollbar handle while you scroll
                t = thumb(img.crop(b))
                if not differs(done_t, t, False):
                    continue                         # same list as last time: nothing new
                if differs(prev_t, t, False):
                    prev_t = t
                    continue                         # list still changing (opening, scrolling): wait a moment
                if done_t is not None and differs(done_t, t, True):
                    title_tries = 0                  # a new shop: fresh tries for its name
                done_t = t
                if region and not (b[0] - region['h'] < region['cols'][0] < b[2] and b[1] - 2 * region['h'] < region['top'] < b[3]):
                    region = None                    # list is somewhere else now: find it again
                set_status('reading')
                rows, _, found = parse_frame(img, self.items, region)
                if found:
                    region = dict(found, edges=edges)
                if not rows:
                    continue
                try:
                    icons.keep(img, rows, (found or region)['h'])   # item pictures for the page
                except Exception:
                    pass                             # a picture is never worth stopping the scan for
                if shop_now is not None and rows[0]['shop'] not in (shop_now, 'Shop'):
                    tracker.reset()                  # a different shop's name: a new visit
                if rows[0]['shop'] != 'Shop' or shop_now is None:
                    shop_now = rows[0]['shop']
                rows = tracker.place(img, found or region, rows) or rows   # every row of the list seen so far
                ev.shop(shop_now, len(rows))
                # rooms change only through portals: look hard on the first shop, then at the watcher's own pace
                # (forcing it on every read cost ~0.35 s per shop and per scroll whenever the minimap was closed)
                room = watcher.update(img, [], force=last_room is None) or state['room'] or 0
                if room != last_room:
                    last_room = room
                    ev.room(room)
                if not state['ch']:
                    set_status('waiting')
                    saver.pending.append((rows, room))
                    if time.time() - nagged > 10:
                        ev.message('Shop seen, but no channel yet. Open the Change Channel window, or type the number.')
                        nagged = time.time()
                    continue
                if rows[0]['shop'] == 'Shop' and title_tries < TITLE_TRIES:
                    title_tries += 1
                    done_t = None                    # name not read: look once more before saving
                    continue
                saver.save(rows, room)
                saver.flush()
