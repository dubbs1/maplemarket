# Sapline

Your EXP, read from your own screen.

**Sapline** is a small Windows app. While you hunt, it looks at the status bar on your screen about once a second and keeps count: EXP per hour, time to the next level, kills by mob (with a picture of each), damage taken, mesos per hour, and a log of every hunt.

It only looks at your screen. It never clicks, types, reads the game's memory or sends anything anywhere.

## Install

1. Open **Releases** (on the right) and download `Sapline-Setup-<version>.exe`.
2. Double-click it. If Windows says "Windows protected your PC", click **More info**, then **Run anyway**.
3. The app opens by itself and starts recording. Keep the game's status bar visible.

Optional: **Tesseract**, a free text reader, lets the app also read the map's name and your meso count for the run log. Settings has a button that installs it.

## What you see

The menu on the left has four pages. The card under it always says what Sapline is doing, with the Start / Stop button.

| Page | What it shows |
|---|---|
| **Home** | EXP per hour and the last 5 minutes, level and progress, time to level, this session's gains, kills, damage taken and mesos, a chart of this session or the last 7 days, and **Next up**: the next 10 % mark, kills to level, kills per hour. Before the first reading it shows what to check |
| **Runs** | The best map, the week's total and the longest run, then one line per hunt: map, level, party, time, EXP/h, mesos/h, kills, damage taken. Rename or delete lines |
| **Mobs** | Your kills by mob as cards, with the picture cut from your screen; name a mob once and it is remembered |
| **Settings** | Start when Sapline opens, log my runs, pause after N minutes, game screen, the text reader, updates, your data, night or day look, and what the app does and never does |

The step-by-step guide, with what you should see at each step, is in [the Guide](Sapline/GUIDE.md).

## Good to know

- Everything stays on your PC, in the folder next to `Sapline.exe`.
- Nexon has not said whether screen readers are allowed. On a private server, ask a GM first. Use at your own risk.
- The earlier Free Market price scanner was retired on 2026-10-28. Its code is kept on the `market-archive` branch.

---

Developers: the app is in `Sapline/`, and the notes on how it all fits together in [CLAUDE.md](CLAUDE.md).
