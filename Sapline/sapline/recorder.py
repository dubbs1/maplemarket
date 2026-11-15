"""The EXP recorder: the thread that takes the screenshots and feeds the EXP tracker. Screenshots only."""
import difflib
import threading
import time
from .capture import Screen
from .exp import ExpWatcher


class Events:
    """What the recorder tells the app (the controller fills these in)."""
    def message(self, text):
        print(text)

    def exp(self, summary):
        pass


class ExpRunner:
    """Records EXP: a screenshot once a second (capture.py), the status bar's EXP line read from it (exp.py) and the party window
    every other second and the meso box spotted every second (location.py, mesos.py); the map's name and the meso
    amount (Tesseract, slow) on a second thread. Runs on its own thread until stop()."""

    def __init__(self, tracker, monitor=1, events=None, every=1.0, capture='auto', meso_dir=None):
        self.tracker, self.monitor, self.every = tracker, monitor, every
        self.meso_dir = meso_dir                      # scans/meso: a record of every meso reading, for reports
        self.screen = Screen(prefer=capture, monitor=monitor)   # the screenshots (capture.py: fast when it works, standard otherwise)
        self.events = events or Events()
        self.watcher = ExpWatcher()
        self._stop = threading.Event()
        self.seen_map = None                          # the map's name must be read the same twice before it counts
        self.latest, self.party_t = None, 0           # the newest screenshot (for the slow reads' thread); the last party look
        self.meso_seen, self.meso_shot = None, None   # what the last meso look found; a picture with the meso box, to be read
        self.lost_since = None                        # since when the status bar hasn't been found (None once it is)

    LOOK_PARTY, LOOK_MESOS, LOOK_MAP, LOOK_CONFIRM = 2, 5, 10, 3   # seconds between looks (the party window and the meso box are
                                                                 # spotted cheaply; reading them needs Tesseract: a thread, see _looks)

    def look(self, img):
        """The map's name (minimap title), the party (its window's HP bars) and the meso box, all at once."""
        self.look_party(img)
        self.look_mesos(img)
        self.look_map(img)

    def look_party(self, img):
        from . import location
        n = location.party_size(img)
        if n:
            self.tracker.set_party(n)

    def spot_mesos(self, img):
        """Every screenshot (cheap, ~50 ms): is the Item window's meso box on screen? If so that very picture goes
        to the slow reads' thread to be read at once, so a window opened for a second or two is never missed.
        `meso_seen` keeps what was found: 'none' (no meso box), 'unread' (the box, but not the number), 'read'."""
        from .mesos import find_box
        box = find_box(img)
        if box:
            self.meso_shot = (img, box)
        elif self.meso_shot is None:
            self.meso_seen = 'none'

    MESO_KEEP = 60                                     # meso box pictures kept in scans/meso (the newest)

    def look_mesos(self, img, box=None):
        """The meso box read (Tesseract): the amount goes to the tracker. Every look is written down in
        scans/meso/meso.log with the box's picture beside it, so a wrong amount can be traced to its picture."""
        try:
            from .mesos import find_box, read_mesos
            box = box or find_box(img)
            if not box:
                self.meso_seen = 'none'
                return
            m = read_mesos(img, box)
            self.meso_seen = 'read' if m is not None else 'unread'
            self._meso_note(img, box, m)
            if m is not None:
                self.tracker.set_mesos(m)
        except Exception:
            self.meso_seen = 'unread'

    def _meso_note(self, img, box, amount):
        if not self.meso_dir:
            return
        try:
            import os
            os.makedirs(self.meso_dir, exist_ok=True)
            stamp = time.strftime('%Y%m%d_%H%M%S')
            name = f'{stamp}_{amount if amount is not None else "unread"}.png'
            x0, y0, x1, y1 = box
            img.crop((max(0, x0 - 40), max(0, y0 - 6), min(img.width, x1 + 60), min(img.height, y1 + 6))).save(os.path.join(self.meso_dir, name), 'PNG')
            with open(os.path.join(self.meso_dir, 'meso.log'), 'a', encoding='utf-8') as f:
                f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")}\t{amount if amount is not None else "unread"}\t{name}\n')
            old = sorted(f for f in os.listdir(self.meso_dir) if f.endswith('.png'))
            for f in old[:-self.MESO_KEEP]:
                os.remove(os.path.join(self.meso_dir, f))
        except OSError:
            pass

    def look_map(self, img):
        """The map's name (Tesseract): a new name counts once read the same twice. True when a name is waiting
        for its second read (the next look comes sooner)."""
        from . import location
        try:
            name = location.read_map(img)
        except Exception:
            name = None
        if not name:
            return bool(self.seen_map)
        known = self.tracker.map
        if known and difflib.SequenceMatcher(None, name.lower(), known.lower()).ratio() >= 0.85:
            self.seen_map = None                       # the same map, read slightly differently
        elif name == self.seen_map:
            self.tracker.set_map(name)
            self.seen_map = None
        else:
            self.seen_map = name
        return bool(self.seen_map)

    def _looks(self):
        """The thread for the slow reads (Tesseract takes a second or two): a meso box spotted by the screenshot
        loop is read at once (and at most every LOOK_MESOS s while the window stays open); the newest screenshot's
        map name every LOOK_MAP s (LOOK_CONFIRM s while a new name waits for its second read). The EXP line is never
        held up."""
        next_mesos = next_map = 0
        while not self._stop.is_set():
            img, now = self.latest, time.time()
            shot = self.meso_shot if now >= next_mesos else None
            if img is None or (shot is None and now < next_map):
                time.sleep(0.25)
                continue
            try:
                if shot is not None:
                    self.meso_shot = None
                    next_mesos = now + self.LOOK_MESOS
                    self.look_mesos(*shot)
                if now >= next_map:
                    next_map = now + (self.LOOK_CONFIRM if self.look_map(img) else self.LOOK_MAP)
            except Exception:
                time.sleep(5)                          # (never stops for good)

    @property
    def found(self):
        """Is the EXP line on screen (the status bar found)?"""
        return bool(self.watcher.bar)

    def stop(self):
        self._stop.set()

    def run(self):
        fails, pause, spent = 0, 0, 0
        self.lost_since = time.time()                 # (the page says how long the EXP line has been missing)
        self.screen.open()
        threading.Thread(target=self._looks, daemon=True, name='look').start()
        try:
            while not self._stop.is_set():
                time.sleep(max(0, self.every - spent))   # (the work of the last round counts: one reading a second)
                t0 = time.time()
                try:
                    img = self.screen.grab()
                    fails = 0
                except Exception:
                    fails += 1                        # (PC locked, a Windows Yes/No prompt): try again shortly
                    time.sleep(2 if fails % 5 == 0 else 0.5)
                    continue
                if time.time() < pause:
                    continue
                try:
                    self.latest = img
                    reading = self.watcher.update(img)
                    now = time.time()
                    if self.watcher.bar:
                        self.lost_since = None
                    if reading and self.tracker.add(reading, now=now):
                        self.events.exp(self.tracker.summary())
                    self.spot_mesos(img)
                    if now - self.party_t >= self.LOOK_PARTY:
                        self.party_t = now
                        self.look_party(img)
                except Exception:
                    pause = time.time() + 30          # a reading that went wrong: never stop for good
                spent = time.time() - t0
        finally:
            self.screen.close()
