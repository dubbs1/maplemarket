"""Builds Sapline.exe (with its _internal folder) using PyInstaller.

  py -3.13 build_app.py            build, then put Sapline.exe and _internal in this folder (build_exe.bat)
  py -3.13 build_app.py --dist D   build into folder D only (the automatic builds, which then make the installer)
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = [('sapline/icon.png', 'sapline'), ('sapline/icon.ico', 'sapline'), ('sapline/app.html', 'sapline')]


def build(dist):
    work = os.path.join(HERE, 'build_tmp')
    sep = ';' if os.name == 'nt' else ':'
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--name', 'Sapline',
           '--icon', os.path.join(HERE, 'sapline', 'icon.ico'), '--workpath', work, '--distpath', dist, '--specpath', work]
    for src, dst in DATA:
        cmd += ['--add-data', os.path.join(HERE, src) + sep + dst]
    subprocess.run(cmd + [os.path.join(HERE, 'app.py')], check=True)
    return os.path.join(dist, 'Sapline')


def main(argv):
    if '--dist' in argv:
        out = build(os.path.abspath(argv[argv.index('--dist') + 1]))
        print('Built', out)
        return 0
    out = build(os.path.join(HERE, 'build_tmp', 'dist'))
    if os.path.isdir(os.path.join(HERE, '_internal')):
        shutil.rmtree(os.path.join(HERE, '_internal'))        # old libraries out, so nothing stale is left behind
    shutil.copytree(out, HERE, dirs_exist_ok=True)
    shutil.rmtree(os.path.join(HERE, 'build_tmp'), ignore_errors=True)
    print('Done. Double-click Sapline.exe to start. Keep the _internal folder next to it.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
