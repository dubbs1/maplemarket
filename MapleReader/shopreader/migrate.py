"""First run of the installed app: bring over scans from an older MapleReader folder (the zip version).

The installed app keeps its data next to itself (in AppData). People who used the zip version have their
scans in a folder like Desktop\\MapleReader. On the very first run, if that folder is found, its scans,
pictures, settings and items.txt are copied over, so nothing is lost and nothing needs importing.
The old folder is left exactly as it was.
"""
import os
import shutil

KEEP = ('settings.json', 'items.txt')            # files next to the app
SKIP_IN_SCANS = ('share_state.json',)            # where sharing got to belongs to that copy only


def candidates(env=None):
    """Folders where an older MapleReader may live, most likely first."""
    env = os.environ if env is None else env
    home = env.get('USERPROFILE') or os.path.expanduser('~')
    bases = [env.get('OneDrive'), env.get('OneDriveConsumer'), os.path.join(home, 'OneDrive'), home]
    out = []
    for base in bases:
        for sub in ('Desktop', 'Documents', 'Downloads', ''):
            if base:
                p = os.path.normpath(os.path.join(base, sub, 'MapleReader'))
                if p not in out:
                    out.append(p)
    return out


def find_old(app_dir, env=None):
    """The older folder with scans in it, or None. Never the app's own folder."""
    here = os.path.normcase(os.path.abspath(app_dir))
    for p in candidates(env):
        if os.path.normcase(os.path.abspath(p)) != here and os.path.isfile(os.path.join(p, 'scans', 'all_scans.txt')):
            return p
    return None


def needed(app_dir):
    """Only on the first run: no scans here yet."""
    return not os.path.exists(os.path.join(app_dir, 'scans', 'all_scans.txt'))


def bring_over(src, dst):
    """Copy the scans folder (and settings, items.txt) from src to dst. Returns how many files were copied."""
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
            if rel == '.' and f in SKIP_IN_SCANS:
                continue
            if rel == '.' and f == 'all_scans.txt':
                continue                                # copied last (below): its being here means "done"
            target = os.path.join(d_scans, rel, f)
            if not os.path.exists(target):
                shutil.copy2(os.path.join(root, f), target)
                n += 1
    main = os.path.join(d_scans, 'all_scans.txt')
    if os.path.isfile(os.path.join(s_scans, 'all_scans.txt')) and not os.path.exists(main):
        shutil.copy2(os.path.join(s_scans, 'all_scans.txt'), main + '.tmp')   # a cut-off copy never counts as done
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
        return f'Could not bring over your scans from {old}: {e}. It tries again next time; or use Options > Older scan files to import them.'
    return f'Brought over your scans from {old} ({n} files). The old folder was not changed.'
