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


def sync_newer(src, dst):
    """Copy the data files (scans/**, settings.json, mobs.txt) that src has and dst lacks, or that are newer in
    src: the old copy may have kept running and writing after the installer copied the data."""
    n = 0
    pairs = [(os.path.join(src, k), os.path.join(dst, k)) for k in KEEP]
    s_scans = os.path.join(src, 'scans')
    for root, _, files in os.walk(s_scans):
        rel = os.path.relpath(root, s_scans)
        pairs += [(os.path.join(root, f), os.path.join(dst, 'scans', rel, f)) for f in files]
    for a, b in pairs:
        try:
            if os.path.isfile(a) and (not os.path.exists(b) or os.path.getmtime(a) > os.path.getmtime(b) + 1):
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copy2(a, b)
                n += 1
        except OSError:
            pass
    return n


def finish_move(app_dir, delay=30, tries=8):
    """The installer moved the app into this folder (the data came along) and left the old folder's path in
    moved_from.txt. The data is synced once more right away (the old copy may have run on for a while after
    the installer's copy), then, once nothing holds the old folder any more, it is renamed (Windows refuses
    that while a file in it is open or a program runs from it) and removed. Tried again at the next start if
    it would not let go. Returns a message or None."""
    marker = os.path.join(app_dir, MOVED)
    try:
        with open(marker, encoding='utf-8-sig') as f:
            old = f.read().strip().rstrip('\\/')
    except OSError:
        return None
    except ValueError:                               # not text: drop it rather than read it every start
        old = ''
    gone = old + '.gone'                             # a half-removed folder from an earlier try
    here = os.path.normcase(os.path.abspath(app_dir))
    old_abs = os.path.normcase(os.path.abspath(old)) if old else ''

    def drop_marker():
        try:
            os.remove(marker)
        except OSError:
            pass
    if not old_abs or old_abs == here or not (os.path.isdir(old) or os.path.isdir(gone)):
        drop_marker()
        return None
    # only a sister folder of the app's own (both under Programs): anything elsewhere is the owner's to delete
    if os.path.dirname(old_abs) != os.path.dirname(here):
        drop_marker()
        return f'Your data came over from {old}. That folder is not needed any more; you can delete it by hand.'
    sync_newer(old, app_dir)                         # before the app reads its files

    def work():
        for _ in range(tries):
            time.sleep(delay)
            if os.path.isdir(gone):
                shutil.rmtree(gone, ignore_errors=True)
            if os.path.isdir(old):
                try:
                    os.rename(old, gone)             # refused while anything in it is open or running
                except OSError:
                    continue
                shutil.rmtree(gone, ignore_errors=True)
            if not os.path.isdir(old) and not os.path.isdir(gone):
                drop_marker()
                return
    threading.Thread(target=work, daemon=True, name='move').start()
    return f'Sapline now lives in {app_dir}. The old folder {old} is being removed.'
