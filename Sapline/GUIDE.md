# Sapline: the guide

Sapline is the window of **Sapline**, a small Windows app that reads your EXP off the game's status bar and keeps count for you. It takes screenshots about once a second and reads them. It never clicks, types, moves the mouse, reads the game's memory or files, or sends anything anywhere.

Nexon has not said whether screen readers are allowed. On a private server, ask a GM first. Use it at your own risk.

## 1. Install

1. Download `Sapline-Setup-<version>.exe` from the project's **Releases** page on GitHub.
2. Double-click it.
   - If Windows says "Windows protected your PC": click **More info**, then **Run anyway**. (The installer isn't signed with a paid certificate; it was built automatically from this project's code.)
   - You should see "Setup - Sapline". Click **Next**, then **Install**, then **Finish** with "Start Sapline" ticked.
3. The window opens on **Home** and waits for you: the card at the bottom left says **Not recording**. Press **Start recording** there. It then says **Looking for the EXP line** until the game's status bar is on screen, then **Recording · Lv 39**. Until then, Home shows the three things to check.
   - If it keeps saying "Looking for the EXP line": make sure the status bar (HP, MP, EXP) is visible and not covered, and that the game is on your main screen (Sapline reads only that one).
4. From now on, open Sapline from the Start menu or the desktop icon.

**Tesseract** (optional). A free text reader. With it installed, the app also reads the map's name and your meso count for the run log. Open **Settings**, and under **Map names and mesos** click **Install Tesseract**. Click **Yes** if Windows asks, wait for "Done" in the black window and close it. The app notices by itself.

## 2. Home

- **The top card**, left to right: EXP per hour (the last 10 minutes), the last 5 minutes and how this hour compares with the hour before; your level, the percentage and how much EXP is left; **Next up**: when you reach the next level at this pace, when you reach the next 10 % mark, and kills left to the level (at the average EXP a kill has given). For the first 5 minutes the numbers show faded with a ≈ in front: too early to mean much.
- **Four tiles**: gained this session (with EXP lost from dying, level-ups and the minutes), kills (counted from each rise of your EXP: one kill, or several when a rise is a multiple of one you have seen), damage taken (with your HP), mesos.
- **The chart**: EXP every 10 minutes, or the last 7 days.
- **Today**: today's total, your best hour, kills per hour, readings skipped.
- **Start recording / Stop recording** is in the card at the bottom left, on every page. Sapline never records until you press Start (unless you switch **Start when Sapline opens** on in Settings). **Reset session** (top right) asks first ("Reset the session? Yes, reset / Keep it") and then starts counting again, for a new hunting trip. **Copy summary** next to it copies this session as a few lines of text (EXP per hour, level, gains, kills, mesos) to paste to a friend or a guild chat.
- With no EXP for a minute (in town, selling, a break), the clock pauses by itself, so EXP per hour stays honest. It carries on at your next EXP gain. Settings sets how long to wait.
- EXP lost from dying is shown apart, not taken off what you gained.
- **Readings skipped** in the Today card counts the seconds the bar could not be read (covered by the mouse or a window). A few now and then is normal.
- If the EXP line has not been seen for half a minute while recording, a card at the top of Home says so, repeats the three checks and offers **Save a screenshot to send**. It goes away by itself once the bar is found.
- The latest message from Sapline (an update, a problem) is one line at the bottom of Home; the last few are in the **Messages** card on the Runs page.

## 3. Runs

Above the log: the best map this week (EXP per hour over its runs), the week's total and the longest run. Then one line per hunt: a new line at a level-up, a new map, or 30 minutes without EXP. Each line keeps the date, map, level, party size, time, EXP/h, mesos/h, kills and damage taken. **Rename** a line to call it what you like, **Delete** to drop it, **Log my runs** switches the log off. **Export CSV** writes the whole log to `runs.csv` in the `scans` folder (Settings, Your data), for Excel or Google Sheets.

The map and the party are read when the minimap and the party window are on screen. Mesos come from the **Item** window: open it at least once in every hunt (at the end is enough: what came in since the last look counts for that hunt), and now and then if you want the rate to follow you during the hunt. A run with no look at it shows — for mesos. What counts: every rise between two looks (pickups, sales); spending is not taken off. A lower amount, or a jump of more than 5,000 (or 5 %), counts only when a second look agrees, so a number read wrong once does not become mesos gained. Every reading is written to `scans\meso\meso.log` with a small picture of the box next to it: if the mesos look wrong, press Save a screenshot, then zip the `scans\meso` folder and send both. (Both need Tesseract.)

**Is this hunt worth it?** Once this hunt has a rate (a few minutes in), a card under the chart puts its EXP an hour and mesos an hour beside your earlier hunts on other maps (from the Runs page, the last 30 days), with the difference from now, and says in one line which map gave the most. If the map name is not read (no Tesseract), the line says "This hunt".

## 4. Settings

- **Start when Sapline opens**: off to begin with. On, Sapline records as soon as it opens.
- **Log my runs**: keep the Runs page's log (also a switch at the top of Runs).
- **Pause after**: how long without EXP before the clock stops (1 to 30 minutes).
- **Screen capture**: how Sapline takes its screenshots. **Fast when possible** uses the picture your graphics card already has (a few milliseconds a grab, and it works when the game is full screen); if that is not available or stops working, Sapline switches to the standard way by itself and the sentence under the setting says why. **Standard** is a plain copy of the screen, the way older versions worked. A change is used from the next Start recording.
- **Your data**: opens the `scans` folder (the run log, the day totals, the screenshots, the meso readings).
- **Save a screenshot**: puts a picture of your screen in that folder. When something is not being read (the mesos, the map, the level), press it while that thing is on screen and send the file.
- **Map names and mesos**: whether the text reader is installed, with the install button.
- **Updates**: see below.
- **Look**: switches between the night and day colours.

## 5. Updates

When a new version is out, a card at the top of Home says **New version …** with a short **What's new** list. Click **Update now**. Sapline closes, updates and opens again by itself within a minute. Your log, pictures and settings stay.

- If it comes back on the same version, the Messages card on the Runs page says the update did not install and why. The details are in `install.log` and `setup.log` in the folder `updates` next to `Sapline.exe` (`%LOCALAPPDATA%\Programs\Sapline\updates`). You can always install a version by hand from the Releases page.
- **Settings** shows which version you have and has a **Check now** button.
- If an older version lived in another folder under `Programs`, an update moves Sapline to `%LOCALAPPDATA%\Programs\Sapline` with your data and removes the old folder about half a minute after the start. On that one update a second Sapline window may open; close either one.
- To remove Sapline: Windows Settings > Apps > Sapline > Uninstall. Your data stays in `%LOCALAPPDATA%\Programs\Sapline\scans` until you delete that folder.

## 6. If something goes wrong

- **"Looking for the EXP line" for a long time**: keep the status bar visible and uncovered, on your main screen. If it still won't read, take a screenshot of the whole game window and send it.
- **The numbers look wrong** (a huge jump, a level that isn't yours): press **Reset**. Readings that don't fit are dropped by themselves, but a bad run of them can take a moment to clear.
- **The window is empty or white**: close it and open Sapline again. It needs Microsoft Edge (every Windows 10/11 PC has it).
- **Mesos stay —**: open the Item window and look at the Mesos tile on Home. "Not seen on screen yet" means the meso box was not found; "can't be read" means it was found but the number was not. Either way, press **Save a screenshot** in Settings while the window is open and send the file.

## 7. The zip version (without the installer)

If you run from a folder instead (Python 3.13 installed as `py -3.13`): double-click `setup.bat` once (Tesseract and the Python packages), then `start_app.bat`. `run_tests.bat` checks the reader against the saved test pictures. `build_exe.bat` builds `Sapline.exe` in the folder.
