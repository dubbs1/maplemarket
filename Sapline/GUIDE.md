# Sapline: the guide

Sapline is the window of **Sapline**, a small Windows app that reads your EXP off the game's status bar and keeps count for you. It takes screenshots about once a second and reads them. It never clicks, types, moves the mouse, reads the game's memory or files, or sends anything anywhere.

Nexon has not said whether screen readers are allowed. On a private server, ask a GM first. Use it at your own risk.

## 1. Install

1. Download `Sapline-Setup-<version>.exe` from the project's **Releases** page on GitHub.
2. Double-click it.
   - If Windows says "Windows protected your PC": click **More info**, then **Run anyway**. (The installer isn't signed with a paid certificate; it was built automatically from this project's code.)
   - You should see "Setup - Sapline". Click **Next**, then **Install**, then **Finish** with "Start Sapline" ticked.
3. The window opens on **Home**. The card at the bottom left says **Looking for the EXP line** until the game's status bar is on screen, then **Recording · Lv 39**. Until then, Home shows the three things to check.
   - If it keeps saying "Looking for the EXP line": make sure the status bar (HP, MP, EXP) is visible and not covered. Check **Game screen** in Settings if the game is on another monitor.
4. From now on, open Sapline from the Start menu or the desktop icon.

**Tesseract** (optional). A free text reader. With it installed, the app also reads the map's name and your meso count for the run log. Open **Settings**, and under **Map names and mesos** click **Install Tesseract**. Click **Yes** if Windows asks, wait for "Done" in the black window and close it. The app notices by itself.

## 2. Home

- **EXP per hour**: EXP per hour (the last 10 minutes), the last 5 minutes, and how this hour compares with the hour before. For the first 5 minutes the numbers show faded with a ≈ in front: too early to mean much.
- **Level**: your level, the percentage, how much EXP is left and when you reach the next level at this pace.
- **This session**: gained (with EXP lost from dying and level-ups), kills, damage taken (with your HP), mesos.
- **Next up**: when you reach the next 10 % mark, kills left to the next level (at the average EXP a kill has given), kills per hour, your best hour and today's total.
- **The chart**: EXP every 10 minutes, or the last 7 days. Bars or a line, normal or log scale.
- **Start recording / Stop recording** is in the card at the bottom left, on every page. **Reset session** (top right) starts counting again, for a new hunting trip.
- With no EXP for a minute (in town, selling, a break), the clock pauses by itself, so EXP per hour stays honest. It carries on at your next EXP gain. Settings sets how long to wait.
- EXP lost from dying is shown apart, not taken off what you gained.
- **Readings skipped** under Next up counts the seconds the bar could not be read (covered by the mouse or a window). A few now and then is normal.

## 3. Runs

Above the log: the best map this week (EXP per hour over its runs), the week's total and the longest run. Then one line per hunt: a new line at a level-up, a new map, or 30 minutes without EXP. Each line keeps the date, map, level, party size, time, EXP/h, mesos/h, kills (hover for which mobs) and damage taken. **Rename** a line to call it what you like, **Delete** to drop it. **Log my runs** switches the log off.

The map and the party are read when the minimap and the party window are on screen. Mesos come from the **Item** window: open it now and then, at least at the start and the end of a hunt. (Both need Tesseract.)

## 4. Mobs

Every rise in your EXP is a kill. A mob always gives the same EXP, so kills are told apart by that amount. A mob you haven't named shows as a card with "22 EXP" and a box: type its name once, click **Save**, and it's kept in `mobs.txt` next to `Sapline.exe` (one mob per line, `name | level | HP | EXP`; you can edit it by hand).

A **picture** of the mob appears after a clear kill: the app compares the screen before and after the kill, and when the camera didn't move and exactly one mob-sized thing vanished for good, that's the mob. Kills that aren't clear (you moved, two mobs died together, a drop was picked up, a map lamp blinked) still count, they just bring no picture that time. If a picture is wrong, press **Not this mob** under it; the next clear kill brings a new one.

In a party, a shared mob gives a different amount each time (the EXP is split by damage), so those kills land under "Other gains", together with quest rewards. Hunting alone, the amounts settle to one per mob.

## 5. Settings

- **Start when Sapline opens**: start recording as soon as the app opens.
- **Log my runs**: keep the Runs page's log (also a switch at the top of Runs).
- **Pause after**: how long without EXP before the clock stops (1 to 30 minutes).
- **Game screen**: which monitor the game is on.
- **Save fight pictures**: only for tuning mob pictures. It stores the screenshots around each kill in `scans\fight` (30 kills at most) and turns itself off when the app next opens. Turn it on for one hunt, zip that folder and send it, if mob pictures come out wrong on your screen.
- **Your data**: opens the `scans` folder (the run log, the day totals, the mob pictures).
- **Map names and mesos**: whether the text reader is installed, with the install button.
- **Updates**: see below.
- **Look**: switches between the night and day colours.

## 6. Updates

When a new version is out, a card at the top of Home says **New version …**. Click **Update now**. Sapline closes, updates and opens again by itself within a minute. Your log, pictures and settings stay.

- If it comes back on the same version, the Messages box says the update did not install and why. The details are in `install.log` and `setup.log` in the folder `updates` next to `Sapline.exe` (`%LOCALAPPDATA%\Programs\Sapline\updates`). You can always install a version by hand from the Releases page.
- **Settings** shows which version you have and has a **Check now** button.
- To remove Sapline: Windows Settings > Apps > Sapline > Uninstall. Your data stays in `%LOCALAPPDATA%\Programs\Sapline\scans` until you delete that folder.

## 7. If something goes wrong

- **"Looking for the EXP line" for a long time**: keep the status bar visible and uncovered; try **Game screen** in Settings. If it still won't read, take a screenshot of the whole game window and send it.
- **The numbers look wrong** (a huge jump, a level that isn't yours): press **Reset**. Readings that don't fit are dropped by themselves, but a bad run of them can take a moment to clear.
- **The window is empty or white**: close it and open Sapline again. It needs Microsoft Edge (every Windows 10/11 PC has it).
- **A wrong mob picture**: press **Not this mob** under it.

## 8. The zip version (without the installer)

If you run from a folder instead (Python 3.13 installed as `py -3.13`): double-click `setup.bat` once (Tesseract and the Python packages), then `start_app.bat`. `run_tests.bat` checks the reader against the saved test pictures. `build_exe.bat` builds `Sapline.exe` in the folder.
