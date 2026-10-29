"""First run of the installed app: bring over the data from an older zip-version folder.

The installed app keeps its data next to itself (in AppData). People who used the zip version have their
scans folder (the run log, day totals, mob pictures) in a folder like Desktop\\Sapline. On the very first
run, if that folder is found, that folder, settings.json and mobs.txt are copied over, so nothing is lost.
The old folder is left exactly as it was.
"""
import os
import shutil
import threading
import time

KEEP = ('settings.json', 'mobs.txt')             # files next to the app
MARK = 'exp_log.json'                            # in scans/: its being here means the data came over (or was made here)
MOVED = 'moved_from.txt'                         # written by the installer when it moved the app to a new folder


def candidates(env=None):
    """Folders where an older zip version may live, most likely first."""
    env = os.environ if env is None else env
    home = env.get('USERPROFILE') or os.path.expanduser('~')
    out = []
    bases = [env.get('OneDrive'), env.get('OneDriveConsumer'), os.path.join(home, 'OneDrive'), home]
    for base in bases:
        for sub in ('Desktop', 'Documents', 'Downloads', ''):
            if base:
                p = os.path.normpath(os.path.join(base, sub, 'Sapline'))
                if p not in out:
                    out.append(p)
    return out


def find_old(app_dir, env=None):
    """The older folder with data in it, or None. Never the app's own folder."""
    here = os.path.normcase(os.path.abspath(app_dir))
    for p in candidates(env):
        if os.path.normcase(os.path.abspath(p)) != here and os.path.isfile(os.path.join(p, 'scans', MARK)):
            return p
    return None


def needed(app_dir):
    """Only on the first run: no run log here yet."""
    return not os.path.exists(os.path.join(app_dir, 'scans', MARK))


def bring_over(src, dst):
    """Copy the scans folder (and settings, mobs.txt) from src to dst. Returns how many files were copied."""
    n = 0
    for name in KEEP:
        if os.path.isfile(os.path.join(src, name)) and not os.path.exists(os.path.join(dst, name)):
            shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
            n += 1
    s_scans, d_scans = os.path.join(src, 'scans'), os.path.join(dst, 'scans')
    for root, _, files in os.walk(s_scans):
        rel = os.path.relpath(root, s_scans)
        os.makedirs(os.path.join(d_scans, rel), exist_ok=True)
        for f in files:
            if rel == '.' and f == MARK:
                continue                                # copied last (below): its being here means "done"
            target = os.path.join(d_scans, rel, f)
            if not os.path.exists(target):
                shutil.copy2(os.path.join(root, f), target)
                n += 1
    main = os.path.join(d_scans, MARK)
    if os.path.isfile(os.path.join(s_scans, MARK)) and not os.path.exists(main):
        shutil.copy2(os.path.join(s_scans, MARK), main + '.tmp')   # a cut-off copy never counts as done
        os.replace(main + '.tmp', main)
        n += 1
    return n


def first_run(app_dir, env=None):
    """Bring older scans over if this is the first run and an older folder exists. Returns a message or None."""
    if not needed(app_dir):
        return None
    old = find_old(app_dir, env)
    if not old:
        return None
    try:
        n = bring_over(old, app_dir)
    except OSError as e:
        return f'Could not bring over your data from {old}: {e}. It tries again next time.'
    return f'Brought over your EXP log and pictures from {old} ({n} files). The old folder was not changed.'


def finish_move(app_dir, delay=10, tries=6):
    """The installer moved the app into this folder (the data came along) and left the old folder's path in
    moved_from.txt. Remove that folder once the setup and its script have let go of it (a few seconds after
    the start; tried again next start if something still held a file). Returns a message or None."""
    marker = os.path.join(app_dir, MOVED)
    try:
        with open(marker, encoding='utf-8') as f:
            old = f.read().strip()
    except OSError:
        return None
    here = os.path.normcase(os.path.abspath(app_dir))
    old_abs = os.path.normcase(os.path.abspath(old)) if old else ''
    # only a sister folder of the app's own (both under Programs), never itself or anything elsewhere
    if not old_abs or old_abs == here or os.path.dirname(old_abs) != os.path.dirname(here) or not os.path.isdir(old):
        try:
            os.remove(marker)
        except OSError:
            pass
        return None

    def work():
        for _ in range(tries):
            time.sleep(delay)
            shutil.rmtree(old, ignore_errors=True)
            if not os.path.isdir(old):
                try:
                    os.remove(marker)
                except OSError:
                    pass
                return
    threading.Thread(target=work, daemon=True, name='move').start()
    return f'Sapline now lives in {app_dir}. The old folder {old} is being removed.'
