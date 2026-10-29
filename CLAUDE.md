# Notes for developers (and Claude Code)

How the project works and the decisions behind it, so new work picks up where the last left off. The user-facing guides are `README.md` and `Sapline/GUIDE.md`.

## Who it's for

- The owner is a beginner on Windows. Give **step-by-step instructions**, one action per step, each with "You should see …" and "If … then …". Plain words; avoid jargon or explain it once.
- Their PC: Windows, Python 3.13 as `py -3.13`, Tesseract 5.5.3 in `C:\Program Files\Tesseract-OCR`; the app installs per user from the Releases page.
- **Updates** reach them through the installer on the Releases page (the app offers them itself); a zip over the folder also works.
- They also run **Rev Market** (vendormarket.app), a separate Ragnarok Online market site on its own server. It must never be touched by this work. Rev Market's design language (clean, everything visible, no hover-only controls, cards never touching) is the standard for this UI too.

## What it is now (2026-10-28)

**Sapline** (until 2026-10-28b: **MapleReader**) is an EXP tracker that reads the game's status bar from screenshots. The Free Market shop scanner and price pages that the project started as were **retired on 2026-10-28** ("extremely tedious" to use); their code (scanner, layout, rows, scroll, names, icons, title, the market page with Prices/Listings/Home, the jsdom checks, the shop fixtures) is kept on the branch **`market-archive`** (= main at merge d81c081, v2026-10-25b) and nowhere else. The program was renamed from MapleReader to Sapline on 2026-10-28 (v2026-10-28c): exe, installer, folder, package (`sapline`), env vars (`SAPLINE_*`), the `X-Sapline` header. The installer keeps MapleReader's **AppId**, so an update over an installed MapleReader keeps its folder (`Programs\MapleReader`) and data, deletes the old exe and shortcuts, and the setup's `[Run]` step starts Sapline (the old update script's restart path points at the gone exe). The release job publishes the installer under **both** names (`Sapline-Setup-<v>.exe` and `MapleReader-Setup-<v>.exe`, each with `.sha256`) so MapleReader 2026-10-28b and earlier can still find an update; drop the copy once the owner is on Sapline. `migrate.first_run` also looks in `%LOCALAPPDATA%\Programs\MapleReader` for a fresh install's data. "Maple Market" was dropped as a name because two live sites use it.

## Hard rules

- **Passive only.** No packet sniffing, no auto-clicking, scrolling or typing, no game-memory reading. Screenshots only. Nexon has not said screen readers are allowed; the guide and the Settings page say so honestly.
- **Don't copy other sites' data** (MeowDB, MesoWatch and others; EXP tables included: the tracker learns each level's EXP from two agreeing readings). Link only.
- **No "MapleStory" in product or domain names** (Nexon's trademark). "Maple" and "meso" are fine. No Nexon artwork.
- **Never edit Rev Market's files, service or server.**
- **Nothing leaves the PC.** No uploads, no telemetry, no cloud.

## How it fits together

```
Game window --screenshots (~1/s)--> recorder.ExpRunner (thread "exp")
   exp.ExpWatcher finds the status bar by colour and reads EXP / % / level / HP by letter shapes (exp_font.py)
   location.read_map + party_size, mesos.read_mesos every 20 s (Tesseract for the map and mesos)
   -> exp.ExpTracker: gained, per hour, time to level, kills, damage taken, runs, goals
   -> scans/exp_log.json (runs), scans/exp_days.json (per day), scans/mobs/<EXP>.png (mob pictures), mobs.txt (names)
   -> server (http://127.0.0.1:8765) -> app window (Edge --app mode) showing app.html (Sapline)
```

### Modules (`Sapline/sapline/`; the package name is historical)

| File | What it does |
|---|---|
| `config.py` | the tuning numbers; `APP_DIR`; `EXP_IDLE` (default pause), `EXP_WARMUP` (5 min: rates shown faded) |
| `engine.py` | Tesseract in-process via ctypes (`libtesseract-5.dll`), self-tests in a throwaway process, falls back to tesseract.exe; `ocr.find_tesseract` finds the install. Only `location.read_map` and `mesos` use it: **EXP works without Tesseract** |
| `colors.py` | `color_boxes`: areas of one UI colour, fast (Pillow); used to find the status bar and the party window |
| `exp.py`, `exp_font.py` | **the EXP tracker.** `find_bar` finds the status bar by the HP (red) and MP (blue, or dark navy when low) fills (`BAR_STEP` 169 at the usual size). `ExpWatcher` never forgets a found bar (after 5 misses it looks again, keeps the old place if nothing is found) and counts `unread` looks. `_boxes`/`classify` cut each character by colour and match it against the game's digit shapes (`exp_font.py`, made by `tools/make_exp_font.py` from the fixtures; the level tiles' font has 3, 7, 8, 9 only: other level digits are never guessed, the level shows "—" until known and level-ups are counted, not re-read). `ExpTracker`: starts when two readings agree; drops readings whose EXP / % disagree with the level's EXP (counted in `skipped`); counts deaths (`lost`) and level-ups apart; just after a level-up a reading is kept only if the level it implies needs ½–2.5× the one before. `pause`/`resume` (Stop/Start) and the idle pause (`idle` seconds without EXP, the `idle_min` setting; the gap is shifted out with `_shift`). `last5`, 10-minute `slots`, `hour`/`prev_hour`/`best_hour`. **Kills** (`_kills`): every rise is one kill or several: an amount seen twice is a mob's EXP; a multiple of one (up to `KILL_MAX` 6, fewest kills wins) or the sum of two is those kills. **Damage taken** (`_hp`): every HP drop between reads with the same full HP. **Mesos** (`set_mesos`): rises between looks; a lower amount counts only when seen twice (`meso_low`). **Runs** (`run`): map, party, level, start; ends at a level-up, `set_map`, `EXP_RUN_GAP` 30 min without EXP, Reset or closing → `ExpLog` (`scans/exp_log.json`, newest first, 300 kept; rename/delete). **Goals** in `summary`: `kills_per_hour`, `kills_left` (EXP left ÷ average EXP per kill), `next_mark` (the next 10 %) with `next_mark_eta`/`_text`, `warm` (under `EXP_WARMUP`). `ExpDays` keeps each day's gain (30 days) |
| `recorder.py` | `ExpRunner`: the thread (screenshots via mss about once a second; a failed grab retries, re-opening mss every 5 misses; an error pauses reading 30 s), feeds the watcher/tracker, calls `look` every `EXP_LOOK_EVERY` for map/party/mesos (a new map counts only when read the same twice), and keeps the last `FRAMES` 5 screenshots for the mob pictures (`saw`: a kill of one amount gets "before"/"earlier" 2 and 3 s back and "after"/"after2"/"after3" 2, 3 and 4 s on; `pending` 3 at most) |
| `location.py` | `read_map` (the minimap title's 2nd line below the orange WORLD button found by `world_buttons`; near-white letters, 12 Tesseract reads voted, 3 must agree; `REGIONS` alone is no map); `party_size` (the party window's red HP bars, same left edge, evenly spaced, at least one long one) |
| `mesos.py` | the Item window's meso box (a white band with a solid gold coin left of it), read with Tesseract, 3 scales, 2 must agree; `MESO_JUMP` 5,000,000 is a misread |
| `mobpics.py` | **mob pictures.** `catch(before, after, after2, earlier, after3)`: under `STILL` 8 % of the screen changed; change map on an 8 px grid; blobs 24–220 px; not within `PLAYER_BAND` 5.5 % of the middle; the spot still between after/after2 and after2/after3 (`GONE_STILL` 4 %); the vanished thing's exact longer side ≥ `MOB_PX` 40 (a picked-up drop is a 32 px icon); changed between earlier and after by at least half as much as before→after (a blinking map lamp fails; the owner's Kerning subway lamp became "the 12 EXP mob" on 2026-10-25); exactly one → its crop from "before" is `scans/mobs/<EXP>.png` (first clear one wins, `KEEP` 300; `forget` drops one). `fight_pics` setting (never saved on) → `save_fight` writes the whole pictures to `scans/fight` (`FIGHT_KEEP` 30) for tuning |
| `mobs.py` | `Mobs` re-reads `mobs.txt` next to the app when its mtime changes (`name | level | HP | EXP`); template written on first run; no list ships (the wiki is CC BY-NC-SA) |
| `controller.py` | the app's state: settings (`monitor`, `exp`, `exp_log`, `idle_min`, `fight_pics`), `exp_start`/`exp_stop`, `snapshot` (the page's `/api/state`: `exp` = `ExpTracker.summary` with `pic` per mob, `exp_days`, `exp_log`, `exp_on`, `exp_found`, `exp_unread`, `update`, events), `mob_name`, `exp_log_edit`, `exp_reset`, `autostart`, updates |
| `server.py` | `AppServer` on 127.0.0.1:8765–8770: `/` (app.html), `/api/state`, `/api/mobpic/<digits>.png` (ASCII digits only), `/favicon.ico`, `/api/ping`; POSTs need the `X-Sapline: 1` header and the local Host (`/api/set`, `exp-reset`, `exp-log`, `mob-name`, `update`, `update-check`, `open-scans`, `install-tesseract`) |
| `desktop.py` | the Edge app-mode window (`WINDOW_TITLE` = `Sapline` = the page's `<title>`; `WINDOW_SIZE` 1240×860; `_lock_window` takes the resize border and Maximise off), `run()` (exits when the window closes or an update installs), `self_check` (`Sapline.exe --self-check out.txt`: starts the parts in a scratch folder; passes without Tesseract) |
| `update.py` | reads the latest GitHub release of `UPDATE_REPO`; needs `Sapline-Setup-<v>.exe` **and** `.sha256` under `https://github.com/<repo>/releases/download/`; `install_script` writes `updates/install.ps1` (run with `-File`, hidden, `CREATE_NO_WINDOW` only) which waits for this process, runs the setup `/VERYSILENT /LOG=updates/setup.log`, logs to `updates/install.log` and restarts Sapline.exe itself if the setup didn't; `Controller` writes `updates/pending.json` and reports at the next start (`_after_update`). Only the installed (frozen) app installs. `SAPLINE_UPDATE_API` = another address (tests) or `off` |
| `migrate.py` | the installed app's first run copies `scans/` (marked by `exp_log.json`), `settings.json` and `mobs.txt` from an older zip folder (Desktop / OneDrive\Desktop / Documents / Downloads `\Sapline`) |
| `app.html` | **the page (Sapline), redesigned 2026-10-29.** One file: Nunito + JetBrains Mono; colours as tokens on `:root` (night = cool slate with gold kept for EXP numbers and the active menu item; day = neutral light), night under `prefers-color-scheme` and `data-theme`, night first unless a choice is stored in localStorage `sap1:theme`. A left menu (`.side`: buttons `data-nav` Home / Runs / Mobs / Settings; a row at phone width) with the **status card** at its bottom: `#chip` ("Recording · Lv 39", "Paused · Lv 39", "Looking for the EXP line", "Reading your EXP…", "Not recording", "Sapline has closed"; `recState()`), a sentence `#chipsub`, and the one Start/Stop button `#go` (`data-x=go`). Each page draws its own header (`head()`: title, a sentence, actions). **Home** (`drawExp`: the update card when there is one; before the first reading `firstOpen()`: "Three things to check" + where the bar is; then the EXP-per-hour card with ▲/▼ vs the hour before, the level card `.xlv` with "Level 40 in about …", four tiles (gained, kills, damage taken, mesos) each with a sentence, the chart (`xr` session/week, `xkind`, `xlog` kept in `sap1:charts`), the **Next up** card (next 10 %, kills to level, kills per hour, best hour, today; "readings skipped" = `exp_unread` + `skipped`), Messages; ≈ and faded numbers while `warm`), **Runs** (`drawRuns`: `weekTiles()` best map / this week / longest run from the last 7 days of the log, the table `.xlog`, rename box `#xrn` not redrawn while typed in, `data-xl`; "Log my runs" in the header), **Mobs** (`drawMobs`: cards `.mob` for this hunt (or the session when no hunt is going) with the picture, EXP, kills, name box `.mn` + Save `data-mns`, **Not this mob** `data-mnx` = forget; the session as a table under it; "Other gains" for amounts seen once), **Settings** (`drawMore`: rows `.opt` with a sentence each: `#ox` `#ol` `#oi` (1–30 min) `#om` `#ofp`, Map names and mesos `#tess`/`#tessgo`, Updates `#updline`/`#updcheck`, Your data `#oscans`, Look `#theme`, the stance text). The page polls `/api/state` once a second (`appPull`) and redraws a page only when its HTML changed (`put`). Opened as a plain file it only says to open Sapline |

**App behaviour:** recording starts when the app opens (`exp` setting, default on). Without Tesseract everything but map names and mesos works; Settings offers the winget install and the controller looks again every 5 s.

## Building and releasing

- **Dependencies are pinned:** `Sapline/requirements.txt` (mss, pillow, pytesseract) and `requirements-build.txt` (+ PyInstaller). Bump them on purpose, run the checks, and audit them (`pip-audit`). The release action is pinned to a commit SHA.
- `Sapline/build_app.py` builds the exe (PyInstaller, `--windowed`, one folder, data: icon.png, icon.ico, app.html); `build_exe.bat` calls it. `Sapline.exe --self-check out.txt` writes PASSED/FAILED; exit code 0 = good.
- `Sapline/installer/Sapline.iss` (Inno Setup 6): per-user install to `%LOCALAPPDATA%\Programs\Sapline`, no admin, Start-menu + desktop icon, `_internal` replaced whole on update, data next to the app kept, `CloseApplications=no` (the update script waits for the app itself).
- `.github/workflows/checks.yml`: **linux** on every push (pyflakes, `run_all.sh`); **windows** on main, PRs, `v*` tags, manual runs, or a commit message containing `[windows]`: the four reader checks with real Windows Tesseract, build exe, self-check, installer + `.sha256`, silent install, self-check the installed copy, a real update while the app runs (through `update.start_install`; the install script's first log line is given up to a minute), uninstall. **release** on main publishes the installer + `.sha256` as `v<__version__>` unless that release exists.
- To release: bump `__version__` in `sapline/__init__.py` and merge to main. (A Claude Code session can't push tags.)
- **On GitHub, plain and short.** A pull request description is one or two sentences saying what changed and why: no headings, bullet lists, checklists, badges, "generated with" lines or session links. Commit messages the same, with only the `Co-Authored-By` line at the end. No comments on pull requests unless there is something to answer. Release notes are GitHub's automatic list of titles.
- Lessons: in the Windows steps never use `Start-Process -Wait` (it also waits for the Sapline the setup starts); wait with `$p.WaitForExit(ms)`. A session's network can't download run artifacts. A private repo's Actions minutes can run out (Windows counts 2×): both jobs then stop 2–4 s after starting with no log.
- **The repository is private:** release downloads need a GitHub login, so the app's updater only works for the owner's own login-free case when releases are public. Making the repo public (or a public releases-only repo pointed at by `UPDATE_REPO`) is the owner's call.

## Checks (run before handing anything over)

**All at once (Linux):** `bash dev-tests/run_all.sh` (`--quick` skips the browser test). It prints one PASS/FAIL line per check.

| What | How |
|---|---|
| On Windows | `Sapline\run_tests.bat`: the EXP reader on the saved pictures, mob pictures, the server, updates |
| On Linux/macOS | `cd Sapline && python3 tests/test_exp.py && python3 tests/test_mobpics.py && python3 tests/test_server.py && python3 tests/test_update.py` |
| In a real browser | `python3 dev-tests/e2e/app_e2e.py` (needs `pip install playwright`; `PW_CHROMIUM=/path/to/chrome` optional): the page with a pretend screen showing a status bar; 41 checks (tile labels render uppercase: compare lowercase) |

Tesseract versions differ (the fixtures were read with 5.3; the owner has 5.5). An `onkeydown` handler on a box must never return `false` for ordinary keys (it cancels the keystroke).

## Known open items

- **Level digits:** the level tiles' font has 3, 7, 8, 9 only. To add digits: put a screenshot with a known status bar in `tests/fixtures`, add it to `SOURCES` in `tools/make_exp_font.py`, run the tool, run `tests/test_exp.py`. At 0.6× interface size the digits are too small: readings are skipped, never wrong.
- **Mob pictures** have no external baseline; a confirmation of new candidates against the kept crop (and a "known junk" set) is the next step if wrong pictures keep appearing.
- **Fixture pictures with a status bar:** live_shop, desk_live, s711 (usual size), ch2, live_ch, shopS (other sizes), status38, status38_lowmp, kerning_inv (mesos, level 39), hunt_party (party of 4), allsold (used by the font tool).
- **Possible next steps** (from the 2026-10-28 research): a local `/overlay` page for OBS; a "copy as picture" session card; CSV export; best EXP/h per map from the run log; all-time kills per mob; Windows notifications; a "report a problem" zip; a small always-on-top card (ask the owner first).
