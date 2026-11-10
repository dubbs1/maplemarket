"""Screenshots of the main screen, two ways, chosen by themselves:

- **fast**: DXcam (Windows Desktop Duplication: the picture the graphics card already has, so a grab costs a few
  milliseconds and works on full-screen Direct3D games too). Windows only; needs the `dxcam` package.
- **standard**: mss (a plain copy of the screen; works everywhere). The fallback, and what `prefer='standard'` asks for.

`Screen.open()` tries the fast way first (unless told not to) and remembers why it couldn't be used (`why`, a sentence
for the Settings page). `grab()` returns a Pillow RGB picture of the whole main screen. If the fast way stops working
while recording (an error, no picture, or only black pictures: a game that took the screen for itself), `grab()`
switches to the standard way by itself and carries on; `how` says which is in use. Screenshots only, like everything
else: nothing is sent anywhere.
"""
import sys
import time
from PIL import Image

FAILS = 3                      # fast grabs in a row that went wrong before the standard way takes over
BLACKS = 5                     # all-black fast pictures in a row (the game took the screen): the standard way takes over
WAIT = 0.05                    # seconds to wait for a first picture from the fast way
PLATFORM = sys.platform        # (the checks pretend to be on Windows)


class Screen:
    """One screen to grab from. `prefer` is 'auto' (fast when it works) or 'standard'."""
    def __init__(self, prefer='auto', monitor=1):
        self.prefer = prefer if prefer in ('auto', 'standard') else 'auto'
        self.monitor = monitor
        self.how = None                                 # 'fast' | 'standard' once open
        self.why = ''                                   # why the fast way isn't in use (empty while it is)
        self.fails = self.blacks = 0
        self._cam = self._sct = self._mon = None
        self.size = None                                # (w, h) of the last picture

    # ---- opening ----
    def open(self):
        if self.prefer == 'standard':
            self.why = 'Standard capture was chosen in Settings.'
        elif PLATFORM != 'win32':
            self.why = 'Fast capture is Windows only.'
        else:
            self.why = self._open_fast()
        if not self.why:
            self.how = 'fast'
        else:
            self._open_standard()
            self.how = 'standard'
        return self

    def _open_fast(self):
        """Try DXcam; the reason it can't be used, or '' when it can."""
        try:
            import dxcam
        except Exception as e:
            return f'The fast capture library is not installed ({type(e).__name__}).'
        try:
            cam = dxcam.create(output_color='BGRA', processor_backend='numpy')
            frame = cam.grab(new_frame_only=False)
            if frame is None:
                time.sleep(WAIT)
                frame = cam.grab(new_frame_only=False)
            if frame is None:
                cam.release()
                return 'Fast capture gave no picture of the screen.'
            self._cam = cam
            return ''
        except Exception as e:
            return f'Fast capture could not start: {type(e).__name__}: {str(e)[:80]}'

    def _open_standard(self):
        import mss
        self._sct = (getattr(mss, 'MSS', None) or mss.mss)()
        self._mon = self._sct.monitors[min(self.monitor, len(self._sct.monitors) - 1)]

    # ---- grabbing ----
    def grab(self):
        """A Pillow RGB picture of the screen. Raises only when the standard way fails too."""
        if self.how is None:
            self.open()
        if self.how == 'fast':
            img = self._grab_fast()
            if img is not None:
                return img
            if self.fails >= FAILS or self.blacks >= BLACKS:
                self._fall_back('Fast capture stopped giving pictures' if self.fails >= FAILS else
                                'Fast capture only saw a black screen (the game has taken the screen for itself)')
            else:
                raise RuntimeError('no picture from the fast capture this time')
        return self._grab_standard()

    def _grab_fast(self):
        try:
            frame = self._cam.grab(new_frame_only=False)
        except Exception:
            self.fails += 1
            return None
        if frame is None:
            self.fails += 1
            return None
        h, w = frame.shape[0], frame.shape[1]
        if not frame.any():
            self.blacks += 1
            return None
        self.fails = self.blacks = 0
        self.size = (w, h)
        return Image.frombuffer('RGB', (w, h), frame.tobytes(), 'raw', 'BGRX', 0, 1)

    def _grab_standard(self):
        if self._sct is None:
            self._open_standard()
        try:
            shot = self._sct.grab(self._mon)
        except Exception:
            self.close_standard()                       # (PC locked, a Windows prompt): a fresh start next time
            raise
        self.size = tuple(shot.size)
        return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')

    def _fall_back(self, why):
        self.why = why + ': standard capture is used from here on.'
        self.how = 'standard'
        self.close_fast()

    # ---- closing ----
    def close_fast(self):
        cam, self._cam = self._cam, None
        if cam is not None:
            try:
                cam.release()
            except Exception:
                pass

    def close_standard(self):
        sct, self._sct = self._sct, None
        if sct is not None:
            getattr(sct, 'close', lambda: None)()

    def close(self):
        self.close_fast()
        self.close_standard()

    def state(self):
        """For the page: {'how', 'why'}."""
        return {'how': self.how, 'why': self.why}
