"""Maple Shop Reader - looks at your screen and writes shop listings to a text file.

It ONLY takes screenshots of your monitor and reads the text in them.
It never clicks, never sends keys, never touches the game's memory or network.
You open the shops yourself.

Run:    py -3.13 maple_shop_reader.py            (or double-click start.bat)
Test:   py -3.13 maple_shop_reader.py --image some_screenshot.png   (or drag it onto test.bat)
Checks: double-click run_tests.bat

The work is done in the shopreader folder:
  config.py    every number you might tune        ocr.py     Tesseract and line reading
  layout.py    finding the shop list               rows.py    reading rows, sold rows, prices
  title.py     reading the shop's name             names.py   cleaning up item names
  location.py  room (minimap) and channel          sound.py   the chime
  session.py   the watching loop and saving
"""
from shopreader.session import main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped.')
