"""Every number you might want to tune, in one place.

Colours are (red, green, blue) as they appear in a screenshot of the game. Times are seconds.
"""
import os
import sys

# The MapleReader folder: next to MapleReader.exe, or the folder holding app.py.
# The scans folder (the EXP log, the day totals, mob pictures), mobs.txt and settings.json live here.
APP_DIR = (os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False)
           else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Tesseract (the text reader: only the map's name and the meso amount need it; EXP itself doesn't) ---
TESS_PATHS = [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
              r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
              os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe')]

# --- updates ---
UPDATE_REPO = 'dubbs1/maplemarket'   # GitHub repository whose releases carry MapleReader-Setup-<version>.exe
UPDATE_EVERY = 6 * 3600        # look for a new version this often while the app is open

# --- EXP tracker ---
EXP_EVERY = 1                  # re-read the EXP line this often (seconds; ~0.1 s of work: a kill is then pinned to the second)
EXP_IDLE = 60                  # no EXP for this long (seconds): the EXP clock stops until the next gain (Options: "Pause after")
EXP_LOOK_EVERY = 20            # read the map's name, the party window and the meso box this often (seconds)
EXP_RUN_GAP = 30 * 60          # no EXP for this long: the EXP log starts a new entry
EXP_SEARCH_EVERY = 5           # look for the status bar this often while it is not found (colour only: fast)
EXP_WARMUP = 5 * 60            # the first minutes of a session: the rates are shown faded (too few readings to mean much)
