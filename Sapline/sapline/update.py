"""Updates: is there a newer Sapline on GitHub, and installing it (the installed app only).

A release carries two files: Sapline-Setup-<version>.exe and Sapline-Setup-<version>.exe.sha256.
The setup file is only run if its SHA-256 fingerprint matches, so a broken or swapped download never runs.
Installing runs that setup quietly once this app has closed; the setup starts Sapline again (and the
install script starts it if the setup didn't, so a failed update never leaves the app closed).
"""
import hashlib
import json
import ntpath
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
SETUP = re.compile(r'^Sapline-Setup-[\w.-]+\.exe$')


def version_key(v):
    """'v2026-10-20f' -> ('2026-10-20', 1, 'f'), so later dates and later letters sort higher."""
    m = re.match(r'^v?(\d{4}-\d\d-\d\d)([a-z]*)$', str(v).strip())
    return (m.group(1), len(m.group(2)), m.group(2)) if m else None


def newer(candidate, current=__version__):
    a, b = version_key(candidate), version_key(current)
    return bool(a and b and a > b)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': f'Sapline/{__version__}', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check(api=None, current=__version__):
    """What the newest release is. state: 'available', 'none' (up to date), 'unavailable' (no public releases
    to look at), or 'offline'. With 'available': version, setup_url, sha_url, page, notes."""
    # SAPLINE_UPDATE_API: another address to ask (the tests' pretend GitHub), or "off"
    url = api or os.environ.get('SAPLINE_UPDATE_API') or API.format(UPDATE_REPO)
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
    req = urllib.request.Request(info['setup_url'], headers={'User-Agent': f'Sapline/{__version__}'})
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


POWERSHELL = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0',
                          'powershell.exe')
INSTALL_LOG, SETUP_LOG, SCRIPT = 'install.log', 'setup.log', 'install.ps1'


def _ps(s):
    return "'" + str(s).replace("'", "''") + "'"           # PowerShell's way of writing ' inside '...'


def install_script(setup_path, pid, app_exe=None):
    """The PowerShell script that waits for this app (process `pid`, and any Sapline.exe still running from
    the app folder) to close, runs the setup quietly with a log, and starts Sapline again if the setup
    didn't. Every step goes to updates/install.log, the setup's own story to updates/setup.log, so a failed
    update can be read about afterwards (the first one on the owner's PC closed the app and left nothing)."""
    folder = ntpath.dirname(setup_path)                   # a Windows path (the tests make one on Linux)
    lines = [f'$log = {_ps(ntpath.join(folder, INSTALL_LOG))}',
             "function Say($t) { ((Get-Date -Format s) + ' ' + $t) | Out-File -FilePath $log -Append -Encoding utf8 }",
             f"Say 'waiting for Sapline (process {int(pid)}) to close'",
             f'Wait-Process -Id {int(pid)} -Timeout 300 -ErrorAction SilentlyContinue']
    if app_exe:
        lines += [f'$exe = {_ps(app_exe)}',
                  'function Running { Get-Process -Name Sapline -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe } }',
                  'for ($i = 0; $i -lt 120 -and (Running); $i++) { Start-Sleep -Seconds 1 }',
                  "if (Running) { Say 'Sapline is still running after 5 minutes: the setup will not be able to replace its files' }"]
    args = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG="' + ntpath.join(folder, SETUP_LOG) + '"'
    lines += ["Say 'running the setup'",
              'try {',                                   # plain CreateProcess, and the error's words if it fails
              '  $psi = New-Object System.Diagnostics.ProcessStartInfo',
              f'  $psi.FileName = {_ps(setup_path)}; $psi.Arguments = {_ps(args)}; $psi.WorkingDirectory = {_ps(folder)}',
              '  $psi.UseShellExecute = $false',
              '  $p = [System.Diagnostics.Process]::Start($psi)',
              "  if ($p.WaitForExit(600000)) { Say ('the setup finished with code ' + $p.ExitCode) } "
              "else { Say 'the setup did not finish in 10 minutes'; $p.Kill() }",
              "} catch { Say ('the setup could not be started: ' + $_.Exception.Message) }"]
    if app_exe:
        lines += ['Start-Sleep -Seconds 5',
                  "if (-not (Running)) { Say 'starting Sapline'; Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) }"]
    lines += ["if ($Error.Count) { Say ('errors: ' + (($Error | ForEach-Object { $_.ToString() }) -join ' | ')) }",
              "Say 'done'"]
    return '\n'.join(lines) + '\n'


def install_command(script_path):
    """Runs the install script hidden. A script file, not -Command, so paths with spaces and quotes need no
    command-line escaping; -ExecutionPolicy Bypass since a PC may forbid scripts otherwise."""
    return [POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
            '-File', script_path]


def start_install(setup_path, pid=None, app_exe=None):
    """Write the script next to the setup and start it. It outlives this app: a hidden console of its own
    (CREATE_NO_WINDOW; DETACHED_PROCESS used to be set as well, which cancels CREATE_NO_WINDOW and leaves
    PowerShell with no console at all), and no handles from this windowed app (a --windowed exe has none)."""
    if sys.platform != 'win32':
        raise OSError('updates install on Windows only')
    script = ntpath.join(ntpath.dirname(setup_path), SCRIPT)
    with open(script, 'w', encoding='utf-8-sig') as f:
        f.write(install_script(setup_path, os.getpid() if pid is None else pid, app_exe))
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    subprocess.Popen(install_command(script), creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=si,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
