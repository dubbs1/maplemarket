# Notes for Claude Code

This project was built in a long claude.ai conversation (October 2026) and moved here. These notes carry what that conversation decided, so new work picks up where it left off.

## Who you're working with

- The owner is a beginner on Windows. Give **step-by-step instructions**, one action per step, each with "You should see …" and "If … then …". Plain words; avoid jargon or explain it once.
- Their PC: the app folder is `C:\Users\bbuda\OneDrive\Desktop\MapleReader`. Python 3.13 runs as `py -3.13`. Tesseract 5.5.3 is in `C:\Program Files\Tesseract-OCR`.
- **Updates:** they extract a zip over the folder ("Replace the files"). When handing over changes, give only the changed files. Send the **full** folder whenever new files were added: a partial zip once left their folder missing `shopreader/config.py`. Now that the code is in git, they may pull instead; ask which they prefer.
- They also run **Rev Market** (vendormarket.app), a separate Ragnarok Online market site on its own DigitalOcean droplet. It must never be touched by Maple work. The owner wants Maple to stand alone, so the group market gets **its own droplet** (decided October 20, 2026); only the DNS record `maple` under vendormarket.app is shared. **DigitalOcean is paused (October 20, 2026):** the owner uses MapleReader locally only for now. Don't push the group market unless they bring it back. Rev Market lives in `/home/market/revenant-market`, `/root/revenant-market` and `/etc/revenant-market.env`. Its design language (clean, everything visible, no hover-only controls, cards never touching, item pictures on rows, "just listed" in green) is the standard for this UI too.

## Hard rules

- **Passive only.** No packet sniffing, no auto-clicking, scrolling or typing, no game-memory reading. Screenshots + OCR only. Nexon has not said screen readers are allowed; the guide says so honestly.
- **Don't copy other sites' data** (MeowDB, MesoWatch, planet-helper and others). Link only.
- **No "MapleStory" in product or domain names** (Nexon's trademark). "Maple" and "meso" are fine.
- **Never edit Rev Market's files, service or droplet.** Maple's droplet is separate; the same-droplet install path still exists but isn't the plan.

## How it fits together

```
Game window --screenshots--> MapleReader (scanner thread)
   reads rows (Tesseract), sold/faded rows, scroll position, room (minimap), channel (Change Channel window)
   -> scans/scan_<date>.txt + scans/all_scans.txt   (one line per listing)
   -> scans/icons/<slug>.png                         (item picture cut from the shop row)
   -> app server http://127.0.0.1:8765 -> app window (Edge --app mode) showing market.html
   -> (sharing on) uploads new lines + pictures to the group server with a personal key
Group server (maple.vendormarket.app, its own droplet, behind nginx + certbot) -> SQLite -> /api/rows feed -> everyone's market page
```

### Scan line format (all_scans.txt, and what the server stores)
`item | price each | shop | room | channel [| sold] [| c<copy>] [| @YYYY-MM-DDTHH:MM:SS±HH:MM]`

- `c2` = the 2nd identical listing in that shop. The reader numbers copies, so two friends scanning the same shop agree and the page merges them.
- The time carries the PC's UTC offset (reader version 2026-10-20c and later), so friends in other time zones agree on ages. Older lines may lack the offset (read as the viewer's local time), `c` or `@time`; the page still imports them. The server needs `@time` and refuses times more than a day in the future.
- Rooms: the wiki lists 11, but the page, server and black window accept 0 to 40 (0 = not read), in case more open at launch.

### MapleReader (`MapleReader/shopreader/`)

| File | What it does |
|---|---|
| `config.py` | every tuning number; `APP_DIR` |
| `engine.py` | Tesseract in-process via ctypes (`libtesseract-5.dll`), about 4× faster; self-tests in a throwaway process, falls back to tesseract.exe; `OMP_THREAD_LIMIT=1` |
| `layout.py`, `rows.py`, `title.py`, `names.py`, `ocr.py` | finding the list, reading rows (normal and faded/sold), shop name, name fixes. A list whose visible rows are **all** sold has no blue row to find it by: `list_boxes` then takes a tall faded block, the layout gets `faded: True`, text is read split black/white at (background grey − 20), and each row is confirmed with `read_row` (fixture `allsold.png`) |
| `scroll.py` | scrollbar handle position, then slot numbers, so long lists of identical items count right (solves the row count N by consistency) |
| `location.py` | room from the minimap; channel from the Change Channel window |
| `scanner.py` | the watching loop (shared by app and CLI), `Saver` (10-minute de-dupe by item+price+room+ch+sold+copy). The room search is forced only on the session's first shop. `color_boxes` (layout.py) does its pixel work in Pillow: a look at a 1440p screen with no shop takes ~13 ms; keep it that way (it runs every 0.15 s) |
| `icons.py` | keeps one picture per item (a clear one replaces a faded one) |
| `controller.py`, `market_server.py`, `desktop.py` | the app: background scanner, local HTTP API (POSTs need the `X-MapleReader: 1` header; Host check), Edge app-mode window, exits when the window closes |
| `update.py` | updates: reads the latest GitHub release of `UPDATE_REPO` (config.py); a release must carry `MapleReader-Setup-<v>.exe` **and** `<that>.sha256`, and the download only runs if the SHA-256 matches. Installing: PowerShell waits for this process to exit, then runs the setup `/VERYSILENT`; the setup's [Run] starts the app again. Only the installed (frozen) app installs; the zip version gets a "Download page" button. `MAPLEREADER_UPDATE_API` = another address (tests) or `off` (all checks set it). Controller field is `update_info` (not `update`: that's the settings method) |
| `migrate.py` | the installed app's first run copies `scans/`, `settings.json`, `items.txt` from an older zip folder (Desktop / OneDrive\Desktop / Documents / Downloads `\MapleReader`), never `share_state.json`, never changing the old folder |
| `share.py` | uploader: tails all_scans.txt from a saved offset (`scans/share_state.json`); survives offline and restarts |
| `market.html` | **the one true copy of the market page.** Run `python tools/sync_market.py` after editing it to copy it to `maple-server/` |

### Market page modes (`MODE` in the page script)

| Mode | When | What it does |
|---|---|---|
| `local` | served by the app (127.0.0.1) | Scan tab, live feed from all_scans.txt, plus friends' rows via `/api/shared/rows` when sharing is on |
| `shared` | served by the group server (sets `window.MAPLE`) | no Scanner tab; live feed from the server |
| `static` | the copy on claude.ai | sample data, manual import |

In live modes the page keeps 30 days in the browser's localStorage (about 40,000 listings fit).

**Simple layout (`SIMPLE`, = live modes; asked for October 20, 2026: "a much easier user experience").** Four tabs: **Scan** (`data-nav=scan`), **Prices** (`browse`: one row per scanned item, cheapest for sale now = seen for sale in the last day), **Listings** (`market`: search + Newest/Cheapest, identical copies merged as "×2") and **More** (`more`: links to `mine`, `deals`, `sources`, plus the import card). The item page (`drawItemSimple`) shows cheapest now / usual / for sale, "Where to buy", and the history behind a `<details>`. The Scan tab has a 3-step checklist that ticks itself, Change buttons for channel/room, Settings folded, and the sharing block only when sharing is already on. The `static` copy keeps the full original layout and demo data (most jsdom checks test that one). Listings shows listings seen in the last 3 days (`RECENT`, "Show older" button); ages and "may be gone" use the **last** sighting (`seen`), "just listed" the first. The item page has a one-click price alert. `say()` messages show as a fading notice at the bottom of the window. `/` focuses search, Esc leaves an item page.

**App behaviour:** the app starts watching when it opens (`auto_start` setting, default on, `Controller.autostart()` from `desktop.run`). Without Tesseract the big button runs the winget installer, and the controller looks again every 5 s, so no restart is needed.

### Group server (`maple-server/`)

- **Code:** stdlib Python + SQLite. `server.py` listens on 127.0.0.1:8790; `manage.py` handles keys (add/list/revoke/restore/purge/stats).
- **Install:** `install.sh` creates its own user/folder/env/service. On a fresh droplet (nothing on ports 80/443) it installs nginx + certbot itself. On a shared server it detects the front door (nginx, Caddy or a Cloudflare tunnel), refuses if another site already uses the address, backs up, validates, rolls back if refused. `--check` changes nothing; `--remove` takes the site down and keeps the data. `MAPLE_DOMAIN` / `MAPLE_EMAIL` set the address and certificate email.
- **Deploy:** `deploy-maple.ps1` (from Windows: tar → scp → ssh → install.sh). It asks for the droplet's login once and remembers it in `deploy-target.json` (not in git). `-Check`, `-Remove`, `-Domain`, `-Email`, `-Server`.
- **Status:** paused (see top). Not installed as of October 20, 2026. The owner follows `maple-server/SETUP.md` (make droplet → DNS → `-Check` → install → keys). This session couldn't reach DigitalOcean or SSH, so the owner runs it.

## Building and releasing

- `MapleReader/build_app.py` builds the exe (PyInstaller); `build_exe.bat` calls it. `MapleReader.exe --self-check out.txt` starts the app's parts in a scratch folder and writes PASSED/FAILED (the exe has no console); exit code 0 = good.
- `MapleReader/installer/MapleReader.iss` (Inno Setup 6): per-user install to `%LOCALAPPDATA%\Programs\MapleReader`, no admin, Start-menu + desktop icon, `_internal` replaced whole on update, data next to the app kept.
- `.github/workflows/checks.yml`: **linux** on every push (pyflakes, `run_all.sh`, install-script checks); **windows** on main, PRs, `v*` tags, manual runs, or a commit message containing `[windows]` (Windows minutes cost 2× on a private repo): reader checks with real Windows Tesseract, build exe, self-check it, build installer + `.sha256`, silent install, self-check the installed copy, uninstall; uploads the installer as an artifact. **release** on a tag `v<__version__>` (the job refuses a mismatch) publishes the installer + `.sha256`.
- To release: bump `__version__` in `shopreader/__init__.py`, merge to main, push tag `v<version>`.
- First green run: October 20, 2026 (run 39400495762, both jobs). Lessons: in the Windows steps never use `Start-Process -Wait` (it also waits for the MapleReader the setup starts: the first run hung for an hour); wait with `$p.WaitForExit(ms)`. Pushes don't cancel each other's runs (concurrency is per commit; only pull requests replace older runs). This session's network can't download run artifacts (blob storage is blocked), so the owner downloads the installer from the run page.
- **The repository is private (October 2026):** release downloads need a GitHub login, so installed apps report "Updates: none published yet". Updates reach users only once releases are public (make the repo public, or publish releases from a public repo and point `UPDATE_REPO` at it). Ask the owner.

## Checks (run before handing anything over)

**All at once (Linux):** `bash dev-tests/run_all.sh` (`--quick` skips pictures and browser tests; `--install` adds the install-script checks, throwaway container only). It prints one PASS/FAIL line per check and fails if any does.

| What | How |
|---|---|
| On Windows | `MapleReader\run_tests.bat`: pictures (tolerant of Tesseract 5.3 vs 5.5), pretend session, scrolling, local server |
| On Linux/macOS | `cd MapleReader && python3 tests/test_pictures.py && python3 tests/test_session.py && python3 tests/test_scroll.py && python3 tests/test_market.py` |
| Market page | `npm install && npm test` (jsdom; 138 checks; t13 runs the app's simple layout via `window.MAPLE={mode:'shared'}`). Keep script lines ≤ 200 characters (a check enforces it) |
| Group server | `python3 maple-server/tests/test_server.py` |
| End-to-end in a real browser | `python3 dev-tests/e2e/<name>.py` (no arguments needed; `app_e2e.py` covers the simple layout), needs `pip install playwright` (`PW_CHROMIUM=/path/to/chrome` optional): `live_e2e.py`, `app_e2e.py`, `share_e2e.py` (pretend friends + server) |
| Install script | `bash dev-tests/e2e/test_install.sh` (28 checks): only in a throwaway container as root, with the stub tools in `dev-tests/e2e/stubs` (fresh droplet, nginx, Caddy, tunnel, address clash, port moves, remove) |
| Deploy script | needs `pwsh`; run it with fake `scp`/`ssh` that run the command locally, against the same stubs |

Tesseract versions differ: the expected outputs were made with 5.3. Linux wheels of `tesserocr` bundle libtesseract 5.5, useful to reproduce the owner's results (point `MAPLEREADER_TESSLIB` at it).

## Known open items

- **Name misreads:** Tesseract 5.5 sometimes reads "Mystery" as "Iystery" on quick re-reads, and single-letter shop names ("S" → "3"). An `items.txt` list fixes names; a shared one via the server is an idea.
- **Stack counts:** the numbers on item icons (e.g. 100) aren't read yet; every listing counts as quantity 1.
- **Fast scrolling:** flicking or dragging straight to the bottom of a long identical list undercounts (by design it never overcounts).
- **Untested for real:** the Windows exe + Edge app window on the owner's PC, and the install on a real droplet (real certbot, real DNS). Ask for screenshots or output on the first run.
- **Possible next steps** (from the October 20 plan): recognise items by their icon to fix misread names; the MapleClassic Wiki item list (CC BY-SA, credit) for names and categories; Windows notifications for alerts; stack counts; a "report a problem" button; CSV export.
