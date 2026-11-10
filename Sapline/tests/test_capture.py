"""Checks the screen capture (capture.py) with pretend libraries: the fast way (DXcam) is used when it works, the
standard way (mss) when it isn't there, won't start, stops giving pictures or only sees black; the setting can force
the standard way; a picture always comes out as a Pillow RGB image of the right size."""
import contextlib, os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from sapline import capture as C                            # noqa: E402

fails = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        fails.append(what)


class Frame:
    """A pretend numpy frame: BGRA bytes, shape (h, w, 4)."""
    def __init__(self, w, h, bgra=(10, 20, 30, 255)):
        self.shape = (h, w, 4)
        self._b = bytes(bgra) * (w * h)

    def tobytes(self):
        return self._b

    def any(self):
        return any(self._b)


class Cam:
    def __init__(self, frames):
        self.frames, self.released, self.grabs = list(frames), False, 0

    def grab(self, new_frame_only=True):
        self.grabs += 1
        f = self.frames.pop(0) if self.frames else self.frames_default()
        if isinstance(f, Exception):
            raise f
        return f

    def frames_default(self):
        return Frame(16, 8)

    def release(self):
        self.released = True


class Shot:
    def __init__(self, w, h):
        self.size, self.bgra = (w, h), bytes((1, 2, 3, 255)) * (w * h)


class Sct:
    def __init__(self):
        self.monitors, self.closed, self.grabs = [{}, {}], False, 0

    def grab(self, mon):
        self.grabs += 1
        return Shot(12, 6)

    def close(self):
        self.closed = True


def fake_dxcam(cam_or_error):
    m = types.ModuleType('dxcam')

    def create(**kw):
        if isinstance(cam_or_error, Exception):
            raise cam_or_error
        return cam_or_error
    m.create = create
    return m


@contextlib.contextmanager
def libs(dxcam, mss):
    """The pretend libraries in place of the real ones for a while (None = not installed)."""
    saved = {k: sys.modules.get(k) for k in ('dxcam', 'mss')}
    for k, v in (('dxcam', dxcam), ('mss', mss)):
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def main():
    print('Screen capture:')
    C.PLATFORM = 'win32'                                     # (the fast way is Windows only: pretend we are there)
    try:
        sct = Sct()
        mss = types.SimpleNamespace(MSS=lambda: sct)

        cam = Cam([Frame(16, 8)])
        with libs(fake_dxcam(cam), mss):
            s = C.Screen().open()
            img = s.grab()
        check(s.how == 'fast' and s.why == '' and img.mode == 'RGB' and img.size == (16, 8) and img.getpixel((0, 0)) == (30, 20, 10),
              f'the fast way when it works: an RGB picture from the BGRA frame ({s.how}, {img.size}, {img.getpixel((0, 0))})')
        check(sct.grabs == 0, 'the standard way is not touched then')

        cam2 = Cam([None, Frame(16, 8)])
        with libs(fake_dxcam(cam2), mss):
            s = C.Screen().open()
        check(s.how == 'fast' and cam2.grabs == 2, 'no picture on the very first grab: asked once more, then fine')

        with libs(None, mss):
            s = C.Screen().open()
            img = s.grab()
        check(s.how == 'standard' and 'not installed' in s.why and img.size == (12, 6) and img.getpixel((0, 0)) == (3, 2, 1),
              f'without the fast library: the standard way, with the reason ({s.why})')

        with libs(fake_dxcam(RuntimeError('No primary output found')), mss):
            s = C.Screen().open()
        check(s.how == 'standard' and 'could not start' in s.why and 'No primary output' in s.why, f'the fast way refusing to start: standard, with the reason ({s.why})')

        cam3 = Cam([None, None])
        with libs(fake_dxcam(cam3), mss):
            s = C.Screen().open()
        check(s.how == 'standard' and 'no picture' in s.why and cam3.released, 'the fast way giving nothing at all: standard, the camera released')

        with libs(fake_dxcam(Cam([])), mss):
            s = C.Screen(prefer='standard').open()
        check(s.how == 'standard' and 'chosen in Settings' in s.why, 'the setting can force the standard way')

        cam4 = Cam([Frame(16, 8), RuntimeError('DXGI_ERROR_ACCESS_LOST'), None, RuntimeError('x')])
        got = []
        with libs(fake_dxcam(cam4), mss):
            s = C.Screen().open()                            # (open() takes the first, good, frame)
            for _ in range(4):
                try:
                    got.append(s.grab().size)
                except RuntimeError:
                    got.append('miss')
        check(got == ['miss', 'miss', (12, 6), (12, 6)] and s.how == 'standard' and cam4.released and 'stopped giving pictures' in s.why,
              f'three failed fast grabs in a row: the standard way takes over and the recording goes on ({got})')

        cam5 = Cam([Frame(16, 8)] + [Frame(16, 8, (0, 0, 0, 0))] * 10)
        sizes = []
        with libs(fake_dxcam(cam5), mss):
            s = C.Screen().open()
            for _ in range(7):
                try:
                    sizes.append(s.grab().size)
                except RuntimeError:
                    sizes.append('black')
        check(sizes[:4] == ['black'] * 4 and sizes[4] == (12, 6) and s.how == 'standard' and 'black screen' in s.why,
              f'only black pictures (the game took the screen): the standard way takes over ({sizes})')

        s.close()
        check(sct.closed, 'close() closes what is open')
        check(s.state() == {'how': 'standard', 'why': s.why}, 'state() for the page')
    finally:
        C.PLATFORM = sys.platform
    if sys.platform != 'win32':
        with libs(fake_dxcam(Cam([Frame(4, 4)])), types.SimpleNamespace(MSS=lambda: Sct())):
            s = C.Screen().open()
        check(s.how == 'standard' and 'Windows only' in s.why, 'not on Windows: the standard way without trying')


if __name__ == '__main__':
    main()
    print()
    if fails:
        print(f'Screen capture: {len(fails)} FAILED')
        sys.exit(1)
    print('Screen capture: all checks passed.')
