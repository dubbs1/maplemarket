# Notes for Claude Code

How the project works and the decisions behind it, so new work picks up where the last left off.

## Who you're working with

- The owner is a beginner on Windows. Give **step-by-step instructions**, one action per step, each with "You should see …" and "If … then …". Plain words; avoid jargon or explain it once.
- Their PC: the app folder is `the MapleReader folder`. Python 3.13 runs as `py -3.13`. Tesseract 5.5.3 is in `C:\Program Files\Tesseract-OCR`.
- **Updates:** they extract a zip over the folder ("Replace the files"). When handing over changes, give only the changed files. Send the **full** folder whenever new files were added: a partial zip once left their folder missing `shopreader/config.py`. Now that the code is in git, they may pull instead; ask which they prefer.
- They also run **Rev Market** (vendormarket.app), a separate Ragnarok Online market site on the same DigitalOcean droplet. It must never be touched by Maple work. Its design language (clean, everything visible, no hover-only controls, cards never touching, item pictures on rows, "just listed" in green) is the standard for this UI too.

## Hard rules

- **Passive only.** No packet sniffing, no auto-clicking, scrolling or typing, no game-memory reading. Screenshots + OCR only. Nexon has not said screen readers are allowed; the guide says so honestly.
- **Don't copy other sites' data** (MeowDB, MesoWatch, planet-helper and others). Link only.
- **No "MapleStory" in product or domain names** (Nexon's trademark). "Maple" and "meso" are fine.
- **Never edit Rev Market's files or service** when working on the droplet.

## How it fits together

```
Game window --screenshots--> MapleReader (scanner thread)
   reads rows (Tesseract), sold/faded rows, scroll position, room (minimap), channel (Change Channel window)
   -> scans/scan_<date>.txt + scans/all_scans.txt   (one line per listing)
   -> scans/icons/<slug>.png                         (item picture cut from the shop row)
   -> app server http://127.0.0.1:8765 -> app window (Edge --app mode) showing market.html
   -> (sharing on) uploads new lines + pictures to the group server with a personal key
Group server (maple.vendormarket.app, behind nginx/Caddy) -> SQLite -> /api/rows feed -> everyone's market page
```

### Scan line format (all_scans.txt, and what the server stores)
`item | price each | shop | room | channel [| sold] [| c<copy>] [| @YYYY-MM-DDTHH:MM:SS]`

- `c2` = the 2nd identical listing in that shop. The reader numbers copies, so two friends scanning the same shop agree and the page merges them.
- Older lines may lack `c` and `@time`; the page still imports them.

### MapleReader (`MapleReader/shopreader/`)

| File | What it does |
|---|---|
| `config.py` | every tuning number; `APP_DIR` |
| `engine.py` | Tesseract in-process via ctypes (`libtesseract-5.dll`), about 4× faster; self-tests in a throwaway process, falls back to tesseract.exe; `OMP_THREAD_LIMIT=1` |
| `layout.py`, `rows.py`, `title.py`, `names.py`, `ocr.py` | finding the list, reading rows (normal and faded/sold), shop name, name fixes |
| `scroll.py` | scrollbar handle position, then slot numbers, so long lists of identical items count right (solves the row count N by consistency) |
| `location.py` | room from the minimap; channel from the Change Channel window |
| `scanner.py` | the watching loop (shared by app and CLI), `Saver` (10-minute de-dupe by item+price+room+ch+sold+copy) |
| `icons.py` | keeps one picture per item (a clear one replaces a faded one) |
| `controller.py`, `market_server.py`, `desktop.py` | the app: background scanner, local HTTP API (POSTs need the `X-MapleReader: 1` header; Host check), Edge app-mode window, exits when the window closes |
| `share.py` | uploader: tails all_scans.txt from a saved offset (`scans/share_state.json`); survives offline and restarts |
| `market.html` | **the one true copy of the market page.** Run `python tools/sync_market.py` after editing it to copy it to `maple-server/` |

### Market page modes (`MODE` in the page script)

| Mode | When | What it does |
|---|---|---|
| `local` | served by the app (127.0.0.1) | Scanner tab, live feed from all_scans.txt, plus friends' rows via `/api/shared/rows` when sharing is on |
| `shared` | served by the group server (sets `window.MAPLE`) | no Scanner tab; live feed from the server |
| `static` | the copy on claude.ai | sample data, manual import |

In live modes the page keeps 30 days in the browser's localStorage (about 40,000 listings fit).

### Group server (`maple-server/`)

- **Code:** stdlib Python + SQLite. `server.py` listens on 127.0.0.1:8790; `manage.py` handles keys (add/list/revoke/restore/purge/stats).
- **Install:** `install.sh` creates its own user/folder/env/service. It detects the front door (nginx, Caddy or a Cloudflare tunnel), backs up, validates, rolls back if refused, and runs certbot for nginx. `--check` changes nothing.
- **Deploy:** `deploy-maple.ps1` (from Windows: tar → scp → ssh root@your-server → install.sh).
- **Status:** not yet installed on the real droplet as of this handoff. The real front door is unknown: run `deploy-maple.ps1 -Check` first.

## Checks (run before handing anything over)

| What | How |
|---|---|
| On Windows | `MapleReader\run_tests.bat`: pictures (tolerant of Tesseract 5.3 vs 5.5), pretend session, scrolling, local server |
| On Linux/macOS | `cd MapleReader && python3 tests/test_pictures.py && python3 tests/test_session.py && python3 tests/test_scroll.py && python3 tests/test_market.py` |
| Market page | `npm install && npm test` (jsdom; 124 checks). Keep script lines ≤ 200 characters (a check enforces it) |
| Group server | `python3 maple-server/tests/test_server.py` |
| End-to-end in a real browser | `dev-tests/e2e/*.py`, needs Playwright (`PW_CHROMIUM=/path/to/chrome` optional): `live_e2e.py`, `app_e2e.py`, `share_e2e.py` (pretend friends + server) |
| Install script | `dev-tests/e2e/test_install.sh`: only in a throwaway container as root, with the stub tools in `dev-tests/e2e/stubs` |

Tesseract versions differ: the expected outputs were made with 5.3. Linux wheels of `tesserocr` bundle libtesseract 5.5, useful to reproduce the owner's results (point `MAPLEREADER_TESSLIB` at it).

## Known open items

- **Name misreads:** Tesseract 5.5 sometimes reads "Mystery" as "Iystery" on quick re-reads, and single-letter shop names ("S" → "3"). An `items.txt` list fixes names; a shared one via the server is an idea.
- **Stack counts:** the numbers on item icons (e.g. 100) aren't read yet; every listing counts as quantity 1.
- **Fast scrolling:** flicking or dragging straight to the bottom of a long identical list undercounts (by design it never overcounts).
- **Untested on the real PC:** the real Windows exe + Edge app window, and the real droplet install. Ask for screenshots or output on the first run.
- **Possible next steps:** stack counts; a shared items.txt; MapleReader auto-update from GitHub releases.
