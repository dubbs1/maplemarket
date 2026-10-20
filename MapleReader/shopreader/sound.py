"""The soft chime played when listings are saved."""
import os
from .config import APP_DIR, CHIME_FILE, VOLUME


CHIME = os.path.join(APP_DIR, CHIME_FILE)   # in the MapleReader folder


def make_chime(path, volume=VOLUME):
    """Write a soft, smooth two-note chime to a small .wav file: pure tones that swell in
    gently, overlap, and fade away to silence (no clicks)."""
    import math, struct, wave
    rate, length = 44100, 1.1
    notes = ((0.0, 1046.5, 1.0), (0.14, 1568.0, 0.75))       # C6 then G6, the second a little softer
    n = int(rate * length)
    frames = bytearray()
    for i in range(n):
        t, v = i / rate, 0.0
        for start, f, amp in notes:
            if t >= start:
                u = t - start
                attack = 0.5 - 0.5 * math.cos(math.pi * min(1.0, u / 0.03))   # 30 ms soft swell
                env = attack * math.exp(-u * 3.2)                              # long, smooth fade
                v += amp * env * (math.sin(2 * math.pi * f * u) + 0.06 * math.sin(4 * math.pi * f * u))
        tail = min(1.0, (length - t) / 0.25)                  # ease the very end down to zero
        v *= 0.5 - 0.5 * math.cos(math.pi * max(0.0, tail))
        frames += struct.pack('<h', int(max(-1.0, min(1.0, v * volume * 0.55)) * 32767))
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(frames))


def beep(volume=VOLUME):
    """Soft chime so you know this shop (or this scroll) is saved and you can move on."""
    try:
        import winsound
        if not os.path.isfile(CHIME) or getattr(beep, 'vol', None) != volume:
            make_chime(CHIME, volume)
            beep.vol = volume
        winsound.PlaySound(CHIME, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass                                          # no sound available: stay quiet
