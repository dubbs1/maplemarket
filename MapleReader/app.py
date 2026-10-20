"""MapleReader with a window: the scanner and the live market together.

Double-click MapleReader.exe (after running build_exe.bat), or start_app.bat.
The black-window version (start.bat) still works and does the same reading.
"""
import sys

if __name__ == '__main__':
    if '--engine-selftest' in sys.argv:              # the exe testing its fast text reader in a throwaway copy
        import os
        os.environ['MAPLEREADER_SELFTEST'] = '1'
        from shopreader.ocr import find_tesseract
        from shopreader import engine
        find_tesseract()
        engine.selftest()
    from shopreader.desktop import run
    run()
