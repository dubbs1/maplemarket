"""Every number you might want to tune, in one place.

Colours are (red, green, blue) as they appear in a screenshot of the game.
Times are seconds. Heights are measured in rows: 1.0 = the height of one shop row.
"""
import os
import re
import sys

# The MapleReader folder: next to MapleReader.exe, or the folder holding maple_shop_reader.py.
# The scans folder, items.txt, settings and the chime file live here.
APP_DIR = (os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False)
           else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Tesseract (the text reader) ---
TESS_PATHS = [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
              r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
              os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe')]
CFG = '-c load_system_dawg=0 -c load_freq_dawg=0'   # don't "correct" item names to dictionary words
SCALE = 2                                            # pictures are enlarged this much before reading

# --- what a shop row looks like ---
PRICE = re.compile(r'^\s*(\d[\d,]*)\s*for\s*([\d,]+)\s*mesos', re.I)
ROW_BG = (205, 217, 227)       # pale blue of a shop's item rows
ROW_FADED = (242, 245, 248)    # near-white of a sold (faded) row
BUTTON_GREY = (177, 177, 177)  # grey channel buttons in the Change Channel window

# --- size of the game's interface ---
# The game's "UI Size" setting and the window size change how tall shop rows are on screen. Reading is tuned
# for rows 54-80 px tall; outside that the shop area is enlarged or shrunk to REF_ROW before reading.
REF_ROW = 63                   # row height (px) the reading is tuned for
ROW_OK = (54, 80)              # rows this tall are read as they are (crisp text reads well at all of these)
LIST_ROWS_WIDE = 4.2           # a shop list's blue area is about this many row heights wide
FADED_ROWS_WIDE = 5.3          # ...and a list of only sold (faded) rows, whose pale area is wider

# --- names ---
NAME_MATCH = 0.85              # how close a read name must be to an items.txt name to be snapped onto it

# --- room (minimap) ---
ROOM_REREAD = 3                # re-read the known minimap spot this often
ROOM_MISSES = 3                # this many failed reads in a row: the minimap moved, search again
ROOM_SEARCH = 5                # look for a lost minimap this often
ROOM_SLOW_SEARCH = 30          # and do the slower text search this often

# --- the watching loop ---
INTERVAL = 0.15                # seconds between screenshots
THUMB = 96                     # size of the tiny picture used to tell if the list changed
PIXEL_CHANGE = 18              # a pixel counts as changed above this brightness difference
CHANGED_LIST = 25              # this many changed pixels in the list area = the list changed
CHANGED_SHOP = 300             # this many = a different shop (ignores small moving sprites)
TITLE_TRIES = 2                # extra looks at a shop whose name could not be read
FORGET_AFTER = 10 * 60         # log the same listing again after 10 minutes

# --- sound ---
VOLUME = 0.08                  # chime loudness, 0.03 (very soft) to 1.0
CHIME_FILE = 'chime2.wav'      # written next to maple_shop_reader.py the first time it plays

# --- updates ---
UPDATE_REPO = 'dubbs1/maplemarket'   # GitHub repository whose releases carry MapleReader-Setup-<version>.exe
UPDATE_EVERY = 6 * 3600        # look for a new version this often while the app is open

# --- EXP tracker ---
EXP_EVERY = 3                  # re-read the EXP line this often (seconds)
EXP_IDLE = 60                  # no EXP for this long (seconds): the EXP clock stops until the next gain
EXP_LOOK_EVERY = 20            # read the map's name and the party window this often while recording EXP (seconds)
EXP_RUN_GAP = 30 * 60          # no EXP for this long: the EXP log starts a new entry
EXP_SEARCH_EVERY = 5           # look for the status bar this often while it is not found (colour only: fast)
