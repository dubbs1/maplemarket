"""Updates: is there a newer MapleReader on GitHub, and installing it (the installed app only).

A release carries two files: MapleReader-Setup-<version>.exe and MapleReader-Setup-<version>.exe.sha256.
The setup file is only run if its SHA-256 fingerprint matches, so a broken or swapped download never runs.
Installing runs that setup quietly once this app has closed; the setup starts MapleReader again.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from . import __version__
from .config import UPDATE_REPO

API = 'https://api.github.com/repos/{}/releases/latest'
SETUP = re.compile(r'^MapleReader-Setup-[\w.-]+\.exe$')


def version_key(v):
    """'v2026-10-20f' -> ('2026-10-20', 1, 'f'), so later dates and later letters sort higher."""
    m = re.match(r'^v?(\d{4}-\d\d-\d\d)([a-z]*)$', str(v).strip())
    return (m.group(1), len(m.group(2)), m.group(2)) if m else None


def newer(candidate, current=__version__):
    a, b = version_key(candidate), version_key(current)
    return bool(a and b and a > b)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': f'MapleReader/{__version__}', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check(api=None, current=__version__):
    """What the newest release is. state: 'available', 'none' (up to date), 'unavailable' (no public releases
    to look at), or 'offline'. With 'available': version, setup_url, sha_url, page, notes."""
    # MAPLEREADER_UPDATE_API: another address to ask (the tests' pretend GitHub), or "off"
    url = api or os.environ.get('MAPLEREADER_UPDATE_API') or API.format(UPDATE_REPO)
    if url == 'off':
        return {'state': 'off'}
    try:
        rel = json.loads(_get(url).decode('utf-8'))
    except urllib.error.HTTPError as e:
        # 404: no release yet, or the repository is private (its releases need a GitHub login)
        return {'state': 'unavailable' if e.code in (401, 403, 404) else 'offline', 'error': f'GitHub answered {e.code}'}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {'state': 'offline', 'error': str(getattr(e, 'reason', e))}
    version = str(rel.get('tag_name', '')).lstrip('v')
    files = {a.get('name'): a.get('browser_download_url') for a in rel.get('assets', []) if isinstance(a, dict)}
    setup = next((n for n in files if n and SETUP.match(n)), None)
    if not version_key(version) or not setup or (setup + '.sha256') not in files:
        return {'state': 'none', 'version': current}       # nothing usable in the release: stay as we are
    if not newer(version, current):
        return {'state': 'none', 'version': current}
    # the files must come from the release page itself (or the tests' pretend GitHub): the fingerprint file only
    # proves the download arrived whole, so nothing else may say where to download from
    u = urllib.parse.urlparse(url)
    allowed = (f'https://github.com/{UPDATE_REPO}/releases/download/',) + ((f'{u.scheme}://{u.netloc}/',) if url != API.format(UPDATE_REPO) else ())
    if not all(str(files[n]).startswith(allowed) for n in (setup, setup + '.sha256')):
        return {'state': 'none', 'version': current}
    return {'state': 'available', 'version': version, 'setup_url': files[setup], 'sha_url': files[setup + '.sha256'],
            'name': setup, 'page': rel.get('html_url', ''), 'notes': str(rel.get('body') or '')[:2000]}


def download(info, folder):
    """Fetch the setup file into `folder` and check its fingerprint. Returns its path; raises ValueError if it
    doesn't match (the file is deleted)."""
    want = _get(info['sha_url']).decode('utf-8', 'replace').split()
    want = want[0].lower() if want else ''
    if not re.fullmatch(r'[0-9a-f]{64}', want):
        raise ValueError('the update has no valid fingerprint')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, os.path.basename(info['name']))
    h = hashlib.sha256()
    req = urllib.request.Request(info['setup_url'], headers={'User-Agent': f'MapleReader/{__version__}'})
    with urllib.request.urlopen(req, timeout=60) as r, open(path, 'wb') as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            h.update(chunk)
            f.write(chunk)
    if h.hexdigest() != want:
        os.remove(path)
        raise ValueError("the download doesn't match its fingerprint, so it wasn't used")
    return path


def install_command(setup_path, pid):
    """The command that waits for this app (process `pid`) to close, then runs the setup quietly. The setup
    replaces the program files (your scans and settings stay) and starts MapleReader again. Waiting for the
    process itself, not a fixed few seconds, means a slow PC never has the setup meet a file still in use."""
    path = setup_path.replace("'", "''")                    # PowerShell's way of writing ' inside '...'
    script = (f'Wait-Process -Id {int(pid)} -Timeout 60 -ErrorAction SilentlyContinue; '
              f"Start-Process -FilePath '{path}' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'")
    return ['powershell', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', script]


def start_install(setup_path):
    if sys.platform != 'win32':
        raise OSError('updates install on Windows only')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)
    subprocess.Popen(install_command(setup_path, os.getpid()), creationflags=flags, close_fds=True)
