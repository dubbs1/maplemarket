"""Sapline with a window: the EXP recorder and its page, Sapline.

Double-click Sapline.exe (after running build_exe.bat), or start_app.bat.
"""
import sys

if __name__ == '__main__':
    if '--engine-selftest' in sys.argv:              # the exe testing its fast text reader in a throwaway copy
        import os
        os.environ['SAPLINE_SELFTEST'] = '1'
        from sapline.ocr import find_tesseract
        from sapline import engine
        find_tesseract()
        engine.selftest()
    if '--self-check' in sys.argv:                  # automatic builds (and support): do the parts start and talk?
        from sapline.desktop import self_check
        i = sys.argv.index('--self-check')
        sys.exit(self_check(sys.argv[i + 1] if len(sys.argv) > i + 1 else 'self_check.txt'))
    from sapline.desktop import run
    run()
