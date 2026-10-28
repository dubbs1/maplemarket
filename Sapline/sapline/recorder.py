"""The EXP recorder: the thread that takes the screenshots and feeds the EXP tracker. Screenshots only."""
import difflib
import threading
import time
from collections import deque
from PIL import Image
from .config import EXP_LOOK_EVERY
from .exp import ExpWatcher


class Events:
    """What the recorder tells the app (the controller fills these in)."""
    def message(self, text):
        print(text)

    def exp(self, summary):
        pass


class ExpRunner:
    """Records EXP: a screenshot about once a second, the status bar's EXP line read from it (exp.py), the map's
    name, party and mesos now and then (location.py, mesos.py), and the pictures around each kill kept for the mob
    pictures (mobpics.py). Runs on its own thread until stop()."""
    FRAMES = 5                                         # screenshots kept (the last few seconds) for the mob pictures

    def __init__(self, tracker, monitor=1, events=None, every=1.0, mobpics=None, fight=None):
        self.tracker, self.monitor, self.every = tracker, monitor, every
        self.events = events or Events()
        self.watcher = ExpWatcher()
        self._stop = threading.Event()
        self.looked, self.seen_map = 0, None          # the map's name must be read the same twice before it counts
        self.mobpics, self.fight = mobpics, fight     # mobpics.MobPics (a picture of each mob killed); fight() = save whole pictures?
        self.frames = deque(maxlen=self.FRAMES)       # (time, screenshot), newest last
        self.pending = []                             # kills waiting for their "after" pictures: {'exp', 'before', 't', 'after'}

    def saw(self, img, now):
        """A new screenshot: a kill just seen gets its "before" pictures (2 and 3 s back), and earlier kills their
        "after" ones (2, 3 and 4 s on); with all, the mob's picture is cut out if the kill was clear (mobpics.catch)."""
        self.frames.append((now, img))
        t = self.tracker
        if t.last_kills and t.gain_t == now and len(t.last_kills) == 1 and t.last_kills[0][1] == 1 and self.mobpics:
            old = [f for f in self.frames if now - f[0] >= 1.8]
            older = [f for f in self.frames if now - f[0] >= 2.8]
            if old:
                self.pending = (self.pending + [{'exp': t.last_kills[0][0], 'before': old[-1][1], 'earlier': older[-1][1] if older else None,
                                                 't': now, 'after': None, 'after2': None}])[-3:]
        done = []
        for p in self.pending:
            if p['after'] is None and now - p['t'] >= 1.8:
                p['after'] = img
            elif p['after'] is not None and p['after2'] is None and now - p['t'] >= 2.8:
                p['after2'] = img
            elif p['after2'] is not None and now - p['t'] >= 3.8:
                frames = (p['before'], p['after'], p['after2'], p['earlier'], img)
                self.mobpics.look(p['exp'], frames)
                if self.fight and self.fight():
                    self.mobpics.save_fight(p['exp'], frames)
                done.append(p)
        self.pending = [p for p in self.pending if p not in done]

    def look(self, img):
        """Every EXP_LOOK_EVERY s: the map's name (minimap title) and the party (its window's HP bars), for the EXP log."""
        from . import location
        n = location.party_size(img)
        if n:
            self.tracker.set_party(n)
        try:
            from .mesos import read_mesos
            m = read_mesos(img)                        # (only while the Item window is open)
            if m is not None:
                self.tracker.set_mesos(m)
            name = location.read_map(img)              # (both need Tesseract; EXP itself doesn't)
        except Exception:
            name = None
        if not name:
            return
        known = self.tracker.map
        if known and difflib.SequenceMatcher(None, name.lower(), known.lower()).ratio() >= 0.85:
            self.seen_map = None                       # the same map, read slightly differently
        elif name == self.seen_map:
            self.tracker.set_map(name)
            self.seen_map = None
        else:
            self.seen_map = name

    @property
    def found(self):
        """Is the EXP line on screen (the status bar found)?"""
        return bool(self.watcher.bar)

    def stop(self):
        self._stop.set()

    def run(self):
        import mss
        sct, fails, pause = None, 0, 0
        try:
            while not self._stop.is_set():
                time.sleep(self.every)
                try:
                    if sct is None:
                        sct = (getattr(mss, 'MSS', None) or mss.mss)()
                        mon = sct.monitors[min(self.monitor, len(sct.monitors) - 1)]
                    shot = sct.grab(mon)
                    fails = 0
                except Exception:
                    fails += 1                        # (PC locked, a Windows Yes/No prompt): try again shortly
                    if fails % 5 == 0 and sct is not None:
                        getattr(sct, 'close', lambda: None)()
                        sct = None
                    time.sleep(2)
                    continue
                if time.time() < pause:
                    continue
                try:
                    img = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
                    if time.time() - self.looked >= EXP_LOOK_EVERY:
                        self.looked = time.time()
                        self.look(img)
                    reading = self.watcher.update(img)
                    now = time.time()
                    if reading and self.tracker.add(reading, now=now):
                        self.events.exp(self.tracker.summary())
                    self.saw(img, now)
                except Exception:
                    pause = time.time() + 30          # a reading that went wrong: never stop for good
        finally:
            if sct is not None:
                getattr(sct, 'close', lambda: None)()
