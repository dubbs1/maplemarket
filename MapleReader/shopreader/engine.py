"""Runs Tesseract. Two ways, same results:

fast: loads Tesseract's own library (libtesseract-5.dll, installed with Tesseract) once and keeps it
      in memory, so each read skips starting tesseract.exe and loading its language files again.
slow: the old way, through pytesseract, which starts tesseract.exe for every single read.

The fast way is used whenever it loads; if anything about it fails, the reader quietly uses the slow way.
Both take the same settings strings, e.g. '--psm 7 -c load_system_dawg=0'.
"""
import atexit
import ctypes
import glob
import os
import re
import sys
import threading
import pytesseract

TSV_COLUMNS = ('level', 'page_num', 'block_num', 'par_num', 'line_num', 'word_num',
               'left', 'top', 'width', 'height', 'conf', 'text')
# Tesseract splits each read across all CPU cores. For small pictures like shop rows that is much
# slower than using one core (2-6x in tests), so ask it to use one. Also applies to tesseract.exe.
os.environ.setdefault('OMP_THREAD_LIMIT', '1')
QUIET = (('debug_file', os.devnull),)                # hide "Estimating resolution as ..." messages
_state = {'lib': None, 'tessdata': None, 'tried': False, 'apis': {}, 'mode': 'slow'}
# One Tesseract handle must never be used by two threads at once (the scanner and "Read a screenshot"
# can both read): that crashes the whole program, not just the read. Reads take turns instead.
_lock = threading.RLock()


def _split(config):
    """'--psm 7 -c a=1 -c b=2' -> (7, (('a', '1'), ('b', '2')))"""
    m = re.search(r'--psm\s+(\d+)', config)
    pairs = tuple(sorted(tuple(v.split('=', 1)) for v in re.findall(r'-c\s+(\S+=\S*)', config)))
    return (int(m.group(1)) if m else 3), pairs


def _candidates():
    """Where libtesseract and its tessdata folder may be. Windows first (next to tesseract.exe)."""
    if os.environ.get('MAPLEREADER_TESSLIB'):         # a specific libtesseract (for testing other versions)
        yield None, os.environ['MAPLEREADER_TESSLIB'], os.environ.get('TESSDATA_PREFIX', '')
    cmd = pytesseract.pytesseract.tesseract_cmd
    folders = []
    if cmd and os.path.isfile(cmd):
        folders.append(os.path.dirname(os.path.abspath(cmd)))
    from .config import TESS_PATHS
    folders += [os.path.dirname(p) for p in TESS_PATHS]
    for d in dict.fromkeys(folders):
        for lib in sorted(glob.glob(os.path.join(d, 'libtesseract*.dll'))):
            yield d, lib, os.path.join(d, 'tessdata')
    if sys.platform != 'win32':                       # Linux/Mac (used by the tests on Claude's side)
        for lib in ('libtesseract.so.5', 'libtesseract.5.dylib'):
            for td in glob.glob('/usr/share/tesseract-ocr/*/tessdata') + glob.glob('/usr/local/share/tessdata'):
                yield None, lib, td


def _safe_on_this_pc():
    """Try the fast way in a separate, throwaway Python first. If Tesseract's library were to crash on
    this PC, only that test process dies and the reader carries on the standard way."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ('import sys; sys.path.insert(0, sys.argv[1]); from PIL import Image; from shopreader import engine; '
            'im = Image.new("L", (120, 40), 255); engine.text(im, "--psm 7"); engine.data(im, "--psm 11"); '
            'print(engine.mode())')
    env = dict(os.environ, MAPLEREADER_SELFTEST='1')
    frozen = getattr(sys, 'frozen', False)            # inside MapleReader.exe: ask the exe to run the test
    cmd = [sys.executable, '--engine-selftest'] if frozen else [sys.executable, '-c', code, root]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return r.returncode == 0 and (frozen or r.stdout.strip().endswith('fast'))
    except (OSError, subprocess.SubprocessError):
        return False


def selftest():
    """Run by 'MapleReader.exe --engine-selftest': exit code 0 if the fast way works here."""
    from PIL import Image
    im = Image.new('L', (120, 40), 255)
    text(im, '--psm 7')
    data(im, '--psm 11')
    os._exit(0 if mode() == 'fast' else 3)


def _load():
    _state['tried'] = True
    if os.environ.get('MAPLEREADER_SLOW_OCR'):
        return
    if not os.environ.get('MAPLEREADER_SELFTEST') and not _safe_on_this_pc():
        return
    for folder, lib, tessdata in _candidates():
        try:
            if folder and hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(folder)          # the DLLs Tesseract needs sit beside it
            L = ctypes.CDLL(lib)
            P, S, I = ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int
            L.TessBaseAPICreate.restype = P
            L.TessBaseAPIInit4.argtypes = [P, S, S, I, ctypes.POINTER(S), I, ctypes.POINTER(S),
                                           ctypes.POINTER(S), ctypes.c_size_t, I]
            L.TessBaseAPIInit4.restype = I
            L.TessBaseAPISetPageSegMode.argtypes = [P, I]
            L.TessBaseAPISetImage.argtypes = [P, S, I, I, I, I]
            L.TessBaseAPIGetUTF8Text.argtypes = [P]
            L.TessBaseAPIGetUTF8Text.restype = P
            L.TessBaseAPIGetTsvText.argtypes = [P, I]
            L.TessBaseAPIGetTsvText.restype = P
            L.TessDeleteText.argtypes = [P]
            L.TessBaseAPIClear.argtypes = [P]
            L.TessBaseAPIDelete.argtypes = [P]
            L.TessBaseAPIEnd.argtypes = [P]
            _state['lib'], _state['tessdata'] = L, tessdata
            if _api(()) is None:                      # can it really start? (finds eng.traineddata)
                _state['lib'] = None
                continue
            _state['mode'] = 'fast'
            return
        except (OSError, AttributeError):
            _state['lib'] = None


def _api(pairs):
    """One Tesseract kept open per set of start-up settings."""
    if pairs in _state['apis']:
        return _state['apis'][pairs]
    L = _state['lib']
    h = ctypes.c_void_p(L.TessBaseAPICreate())
    allp = pairs + QUIET
    keys = (ctypes.c_char_p * len(allp))(*[k.encode() for k, _ in allp])
    vals = (ctypes.c_char_p * len(allp))(*[v.encode() for _, v in allp])
    ok = L.TessBaseAPIInit4(h, _path(_state['tessdata']), b'eng', 3, None, 0, keys, vals, len(allp), 0)
    if ok != 0:
        L.TessBaseAPIDelete(h)
        return None
    _state['apis'][pairs] = h
    return h


@atexit.register
def _close():
    """Shut Tesseract down cleanly when the reader stops (but never hold up closing for it)."""
    if not _lock.acquire(timeout=5):
        return                                       # a read is still running: let the process end anyway
    try:
        L = _state['lib']
        for h in _state['apis'].values():
            if h is not None:
                L.TessBaseAPIEnd(h)
                L.TessBaseAPIDelete(h)
        _state['apis'].clear()
    finally:
        _lock.release()


def mode():
    """'fast' or 'slow' - shown when the reader starts."""
    if not _state['tried']:
        with _lock:
            if not _state['tried']:
                _load()
    return _state['mode']


def use(which):
    """Switch engines: 'slow' (--slow-ocr, and the tests) or 'fast' (back on, if it loads)."""
    if which == 'slow':
        _state['tried'], _state['mode'] = True, 'slow'
    elif _state['lib'] is not None:
        _state['mode'] = 'fast'
    else:
        _load()
    return _state['mode']


def _path(p):
    return p.encode('mbcs' if sys.platform == 'win32' else 'utf-8')


def _run(img, config, tsv):
    with _lock:
        return _run_locked(img, config, tsv)


def _run_locked(img, config, tsv):
    psm, pairs = _split(config)
    h = _api(pairs)
    if h is None:
        return None
    L = _state['lib']
    if img.mode not in ('L', 'RGB'):
        img = img.convert('RGB')
    bpp = 1 if img.mode == 'L' else 3
    L.TessBaseAPISetPageSegMode(h, psm)
    L.TessBaseAPISetImage(h, img.tobytes(), img.width, img.height, bpp, img.width * bpp)
    p = L.TessBaseAPIGetTsvText(h, 0) if tsv else L.TessBaseAPIGetUTF8Text(h)
    out = ctypes.string_at(p).decode('utf-8', 'replace') if p else ''
    if p:
        L.TessDeleteText(p)
    L.TessBaseAPIClear(h)
    return out


def text(img, config=''):
    """Like pytesseract.image_to_string."""
    if mode() == 'fast':
        out = _run(img, config, False)
        if out is not None:
            return out
    return pytesseract.image_to_string(img, config=config)


def data(img, config=''):
    """Like pytesseract.image_to_data(..., output_type=DICT): one entry per word with its box."""
    if mode() == 'fast':
        out = _run(img, config, True)
        if out is not None:
            d = {c: [] for c in TSV_COLUMNS}
            for line in out.splitlines():
                parts = line.split('\t')
                if len(parts) < 11:
                    continue
                parts += [''] * (12 - len(parts))
                for c, v in zip(TSV_COLUMNS, parts):
                    d[c].append(v if c == 'text' else float(v) if c == 'conf' else int(v))
            return d
    return pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
