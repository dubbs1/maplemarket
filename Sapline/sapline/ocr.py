"""Tesseract: finding it (the map's name and the meso amount are read with it; the EXP line isn't)."""
import os
import shutil
import pytesseract
from .config import TESS_PATHS


def find_tesseract():
    """The current Windows installer no longer adds Tesseract to PATH, so look in the usual folders."""
    if shutil.which('tesseract'):
        return True
    for p in TESS_PATHS:
        if os.path.isfile(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return False
