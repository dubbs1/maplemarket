# Reading Maple shops safely: what is and isn't known

**Nobody, including Nexon, has confirmed whether a tool that only takes screenshots and reads text is safe or banned in MapleStory Classic World, so the honest answer is "unknown, use at your own risk."** I could not retrieve Nexon's current Terms of Use, Rules of Conduct or any Classic-specific support page, so there is no quoted rule for or against passive screen reading. What Nexon does say publicly is that hacking, botting and "any type of game manipulation" earn bans, and that an automated system called Nexon Game Security (NGS) plus Game Master reviews decide them. Your tool (maple_shop_reader.py) sits outside those categories by design: it takes screenshots and reads text, and it never clicks, sends keys, or touches game memory or network traffic. Setup is simple for a beginner on Windows: install Tesseract (it no longer adds itself to PATH, which your script handles), run setup.bat, test on a screenshot, then run start.bat while you open shops yourself. The OCR approach you use (crop, enlarge, clean up, read, then require two matching reads) follows Tesseract's own advice, but the exact tuning values are starting points, not proven numbers. Classic World already has many price sites, so yours competes on being self-made and fed by your own scans. The step-by-step guide is at the end of this report.

## Nexon's public rules say "hacking and botting," and say nothing about screen readers

The most important finding is a gap. The Nexon Terms of Use, Rules of Conduct and Classic support-center pages did not load for the research (they are built with JavaScript and returned only page metadata), so **no verbatim rule on third-party programs was obtained**, and no Classic-specific "unauthorized programs" article turned up. The generic wording that was retrieved is this: Nexon's Game and Account Ban FAQ lists "hacking, botting" as example ban reasons, says bans come from Game Master review of in-game evidence or from the automated NGS system, and says its evidence is proprietary and not shared; bans with insufficient evidence are released and appeals go through the support portal ([Nexon Support](https://support-maplestory.nexon.com/hc/en-us/articles/360000440123-Game-and-Account-Ban-FAQ)). An August 5, 2026 Nexon America memo about the main MapleStory game banned players who "manipulated the game to clear boss content" and said "any type of game manipulation" violating the Terms "will not be tolerated" (quote as rendered by the reporter) ([MassivelyOP](https://massivelyop.com/2026/08/06/maplestory-cracks-down-on-cheaters-as-maplestory-classic-world-test-keys-pop-up-on-ebay-for-over-300/)). The only Classic-related enforcement notices found concern unauthorized access to a closed test and unauthorized servers, not third-party tools ([Nexon notice](https://www.nexon.com/maplestory/news/general/40325/regarding-unauthorized-access-to-closed-online-test)).

Two things follow. First, Nexon enforces actively and does not explain its detection, so "nobody has been banned for this" is not the same as "this is allowed." Second, penalties may reach beyond Classic: a fan guide citing Nexon's own report says a penalty in either Classic World or modern MapleStory applies to both because they share a Nexon account ([MeowDB](https://meowdb.com/msclassic/guides/what-is-maplestory-classic-worlds)). Treat your main account as the thing at stake.

On anti-cheat itself, NGS is the named system for MapleStory generally, but **whether Classic World uses NGS, or something else, is unconfirmed**; one fan guide says only that Classic has an "anti-cheat system" with no name or detail ([MeowDB](https://meowdb.com/msclassic/es/guides/what-is-maplestory-classic-worlds)). No source documents it blocking screen-capture methods. The one risk signal is anecdotal: in 2023 (live MapleStory, on Steam) players reported "illegal program detected" false positives, with one commenter claiming ordinary software such as OBS had been flagged, and another saying it usually meant a warning or kick rather than a ban ([Steam discussion](https://steamcommunity.com/app/216150/discussions/0/5956623715029862427)). That suggests running processes can be scanned, which is a reason to keep your tool minimal, not evidence that OCR tools are targeted. I found no reports of bans or warnings for OCR or price-reading tools in either game, but Reddit and Discord could not be searched, so that silence is weak evidence. A vendor blog claiming memory scanning and behavior analysis was low-reliability and never mentioned screen capture ([ExitLag](https://www.exitlag.com/blog/maplestory-artale-hack/)).

**What to do about it:** read Nexon's current Terms of Use and Rules of Conduct (nexon.com legal pages) and the MapleStory Classic support center yourself, and consider asking Nexon support directly before relying on the tool. Do not use it on an account you cannot afford to lose. As a precaution, which is unverified and not a Nexon rule, keep the tool to screenshots only and avoid adding any automatic clicking or typing.

## How shops and the Free Market work, and what your reader must handle

Classic World has two kinds of shop. A Store needs a cash-shop permit, requires you to stay logged in, and closes if a monster attacks or kills you; a Hired Merchant keeps selling while you are offline, can only be set up in the Free Market, and is removed automatically after 24 hours ([mapleclassic.wiki](https://mapleclassic.wiki/wiki/Player_shop)). The wiki lists **16 listing slots** on the Regular permit and 24 on the seasonal ones, though other sources say 12 or 18, so slot counts should not be hard-coded ([mapleclassic.wiki](https://mapleclassic.wiki/wiki/Player_shop); [MeowDB](https://meowdb.com/msclassic/item-db/1540); [U4N](https://www.u4n.com/news/maplestory-classic-world-free-market-prices-what-items-are-worth-and-how-to-trade-smarter.html)). Hired Merchants had a bug in August 2026 (stats lost on equipment collected from closed shops), reported fixed after maintenance ([MeowDB](https://meowdb.com/msclassic/news/second-cot-hired-merchant-fix)).

The Free Market is split into rooms. The wiki documents **11 rooms**, named "Free Market (1)" to "(11)," entered from Perion and Henesys, and states that "nothing in the game indexes the stalls," so buyers must walk room to room ([mapleclassic.wiki](https://mapleclassic.wiki/wiki/Free_Market)). That is why third-party trackers exist. Shops also differ by channel: one live tracker shows entries like "channel 17 · room 10," implying at least 17 channels ([freemarketclassic.com](https://freemarketclassic.com/?hl=en)). The channel is not on the minimap, which is why your tool asks you to type it, the same trade-off the open-source scanner mfm-tracker makes (it asks the user or reads the Change Channel window) ([mfm-tracker README](https://raw.githubusercontent.com/jayee88/mfm-tracker/main/README.md)). Room counts and channel counts may change at launch, so the tool's "room 9" override and free-typed channel are the right design. Founder's Access began October 6 and Grand Launch is **October 21, 2026**, with early-access progress carrying forward, so a launch-day surge of shops is likely ([MassivelyOP](https://massivelyop.com/2026/08/24/maplestory-classic-world-opens-its-doors-to-founders-october-6-and-to-everyone-else-october-21/); [MeowDB](https://meowdb.com/msclassic/news/ossyria-report-confirms-october-launch)).

Several price details are **unverified for Classic**, and they matter for your site. Whether a shop price is per bundle or per item is not documented in any Classic source I could read; old MapleStory entered prices per bundle, but treat that as something to confirm in-game. Your tool's "price each" column should be checked against a real multi-item listing before you trust the Deals tab. The sales fee is also unclear: a China-test article says the trading fee fell from 10% to 5%, without saying it applies to shops or to Global ([MeowDB](https://meowdb.com/msclassic/es/news/cms-cbt2-opening-details)). Sold rows appear to stay in the window but faded, according to the mfm-tracker author, who logs faded listings as sold ([README](https://raw.githubusercontent.com/jayee88/mfm-tracker/main/README.md)). Your tool cannot detect sold rows, so every scan may include items already sold; importing scans as snapshots, as the site does, is a sensible way to live with that. Stack counts drawn on item icons are also not read, so quantities in your data are incomplete.

## How the OCR works, and which tricks matter most

Tesseract is designed for text of roughly 300 DPI, so tiny game fonts usually need enlarging first; it prefers dark text on a light background in version 4 and later, can fail on tightly cropped text (add a small border, about 10 pixels in the docs' example), and its built-in black-and-white conversion can struggle with uneven backgrounds ([Tesseract docs](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)). A practitioner reading small game text found enlarge first, then convert to black and white, worked best; they used 3.5x but advised trying 2x to 2.5x if digits blur (a slashed zero turning into an 8) ([AutoHotkey forum](https://www.autohotkey.com/boards/viewtopic.php?p=218148)). Practical starting values, which are my suggestions and not verified: enlarge 3x (try 2x and 4x), convert to grayscale, threshold, and flip so text is dark on light. A highlighted orange row is the classic trap because its background changes the contrast; your test on a real screenshot read that row correctly, which is the right kind of check.

Reading mode matters too. Tesseract's "page segmentation modes" tell it what layout to expect: 7 for a single text line, 6 for a uniform block, 11 for sparse text ([Tesseract docs](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)). For prices and item names the docs suggest turning off the dictionaries (`load_system_dawg` and `load_freq_dawg` set to 0), because words like "Cutlass" are not ordinary dictionary words ([Tesseract docs](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)). Limiting digits with `tessedit_char_whitelist` helps on number-only cells, but it stopped working in some early version 4 builds and was not confirmed for 5.x, and over-filtering can corrupt text ([issue #751](https://github.com/tesseract-ocr/tesseract/issues/751); [PyImageSearch](https://pyimagesearch.com/2021/09/06/whitelisting-and-blacklisting-characters-with-tesseract-and-python/)). Safer is to read freely, then clean numbers with simple rules (strip commas, and swap look-alike letters only inside number fields).

Reliability and speed come from workflow rather than settings. The `image_to_data` function returns each word with its position (needs Tesseract 3.05 or later), so words can be grouped into rows ([pytesseract](https://github.com/madmaze/pytesseract)). Your design choices (skip the slow read when the screen has not changed, require two matching reads, avoid re-logging a listing for 10 minutes) are the standard lightweight approach; no timing benchmarks were found, so the "few seconds per shop" figure is your own estimate. Name correction against an items.txt list is best done with fuzzy matching and a strict cutoff, flagging anything below it as unknown instead of guessing; the rapidfuzz library's `extractOne` with a `score_cutoff` is built for this ([RapidFuzz docs](https://rapidfuzz.github.io/RapidFuzz/Usage/process.html)). Tiny outlined stack numbers are a different problem; the usual fix is matching against saved images of each digit with OpenCV, which does not rescale automatically, so the saved digits must be at the screen's native size ([OpenCV docs](https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html); [OpenCV forum](https://forum.opencv.org/t/i-want-opencv-to-recognize-the-numbers-on-the-game-screen/17106)). That is a sensible future upgrade for your known stack-count limit. If Tesseract disappoints, lighter-to-install alternatives exist (Windows built-in OCR through `winocr`, or RapidOCR), but none has been tested on pixel fonts ([PyPI winocr](https://pypi.org/project/winocr); [PyPI rapidocr](https://pypi.org/project/rapidocr/)).

## What gets installed, and the Windows traps for beginners

The latest Windows Tesseract installer from the UB-Mannheim project is **5.5.3.20260724** (64-bit only); the wiki says the "add to PATH" option was disabled in the latest version and recommends installing to the suggested folder ([UB-Mannheim wiki](https://github.com/UB-Mannheim/tesseract/wiki)). Windows will therefore not find Tesseract by name, which is why your script looks in `C:\Program Files\Tesseract-OCR\tesseract.exe`. Without that, pytesseract's default is to look for a plain `tesseract` on PATH and raises "TesseractNotFoundError" when it cannot ([pytesseract source](https://raw.githubusercontent.com/madmaze/pytesseract/master/pytesseract/pytesseract.py)). The default folder is widely used in guides, though the wiki itself did not state it, and English comes with the standard installer (also from background knowledge, not verified here).

For Python, the docs recommend `python -m pip` over bare `pip`, and `py -3.13` selects version 3.13, both of which work without changing PATH ([Python docs](https://docs.python.org/3/using/windows.html)). That is exactly what setup.bat does. The three packages suit Python 3.13: Pillow 13.0.0 (16 October 2026) has a 3.13 Windows wheel, so no compiler is needed ([PyPI pillow](https://pypi.org/project/pillow/)); mss 10.2.0 (April 2026) is a screen-capture library ([PyPI mss](https://pypi.org/project/mss/)); pytesseract 0.3.13 dates from August 2024 and its listed support stops at Python 3.12, though it is pure Python and nothing found says it breaks on 3.13 ([PyPI pytesseract](https://pypi.org/project/pytesseract/)). I did not test an actual install, so setup.bat's output is the real check.

Capture has three known hazards. mss treats monitor 0 as all screens combined and monitor 1 as the first one ([mss docs](https://python-mss.readthedocs.io/api.html)). Windows display scaling (125% or 150%) can make coordinates and screenshots disagree, which is background knowledge rather than a confirmed finding, so judge regions by looking at a saved image. And exclusive fullscreen DirectX games commonly give black or frozen captures to this style of tool, so windowed or borderless windowed is the usual advice; that is unverified in sources, but mfm-tracker likewise supports windowed or borderless only ([README](https://raw.githubusercontent.com/jayee88/mfm-tracker/main/README.md)). One more Windows trap: Notepad can save a file as `reader.py.txt`, which will not run, so show file extensions and use "All files" when saving.

## Many price sites already exist, so your edge is control and honesty about data

Classic World already has a crowded set of community tools, most launched within weeks. MeowDB (becoming NiaDB) shows player-reported prices with charts, price alerts, and a Discord bot ([MeowDB](https://meowdb.com/msclassic/free-market)). maplestory-classic.com reports 902 items and about 349,708 live listings as of October 15 with a JSON feed ([maplestory-classic.com](https://maplestory-classic.com/market)). freemarketclassic.com and Meso Scout list shops with seller, channel and room ([freemarketclassic.com](https://freemarketclassic.com/?hl=en); [mesoscout.com](https://mesoscout.com/)). planet-helper offers player-posted listings and a screenshot price check, but its footer forbids copying, automated collection and AI training on its data ([planet-helper](https://planet-helper.com/gmsclassic/market/)). EvilEyeFM and maplestory.quest are also live, with little published detail ([evileyefm.com](https://evileyefm.com/); [maplestory.quest](https://maplestory.quest/market/shops)). Several tool names that were suggested to the researchers (MesoWatch, Sleepywood, MESOLANE, maple.community, Maple Helper, nooseking) could not be found and should be treated as unverified.

The closest relative to your tool is **mfm-tracker**, an open-source (GPL v3) Python desktop app that also uses mss, Tesseract and pytesseract. It captures about every 0.15 seconds, finds the shop and minimap windows itself, flags deals against a 14-day median, logs faded rows as sold, and claims about 0.8% character error with a custom OCR model versus 5.6% stock ([GitHub](https://github.com/jayee88/mfm-tracker)). That is a useful benchmark and a source of ideas, though it is far more elaborate than yours. Its existence also shows that others are running passive screen-reading scanners on Classic, though that is not evidence of safety.

Two practical cautions for your own site. The wiki's data is licensed CC BY-NC-SA 4.0, so a monetised site should not copy it ([mapleclassic.wiki](https://mapleclassic.wiki)), and other sites' data should not be scraped without checking their terms; your own scans avoid both problems. And because your tool lacks stack counts and sold detection, label the site's numbers as "asking prices seen in shops" rather than market prices.

## Conclusion

The central finding is a boundary rather than a verdict: your tool avoids everything Nexon has named as bannable (hacks, bots, input automation, game manipulation), yet no source says that screen reading is permitted, and Nexon keeps its detection criteria secret. That makes this a risk you accept knowingly, not a rule you have confirmed you are following. The sensible stance is to read Nexon's current rules, keep the tool strictly passive, and avoid putting an account you value on the line.

The more actionable discovery is how much of the data problem is still open. Bundle-versus-each pricing, the shop fee, and sold-row appearance are not documented for Classic, and your tool cannot see stack counts or sold rows. Check one real multi-item shop in-game before you trust the Deals tab, and consider digit template matching later to close the stack-count gap.

---

# The easy way: the MapleReader installer

The installer needs nothing else first (no Python, no `setup.bat`, no `build_exe.bat`). Updates then come by themselves.

1. Download `MapleReader-Setup-<version>.exe` from the project's **Releases** page on GitHub (or from the file Claude sends you).
2. Double-click it.
   - If Windows says "Windows protected your PC": click **More info**, then **Run anyway**. (The installer isn't signed with a paid certificate; it was built automatically from this project's code.)
   - You should see "Setup - MapleReader". Click **Next**, then **Install**, then **Finish** with "Start MapleReader" ticked.
3. MapleReader opens on the **Scan** tab and starts watching.
   - If you used the zip version before, the first message says `Brought over your scans from ...`: everything you scanned is already there. The old folder isn't changed; you can delete it later.
   - If the big button says **Install Tesseract**, click it (see Part G2).
4. From now on, open MapleReader from the Start menu or the desktop icon.
5. **Updates:** when a new version is out, a card at the top of the Scan tab says **A new version is ready**. Click **Update now**. MapleReader closes, updates and opens again by itself within a minute. Your scans and settings stay.
   - Settings (on the Scan tab) shows `Updates: ...` and has a **Check now** button.
   - To remove MapleReader: Windows Settings > Apps > MapleReader > Uninstall. Your scans stay in `%LOCALAPPDATA%\Programs\MapleReader\scans` until you delete that folder.

6. **Your EXP:** while MapleReader is watching, the **Your EXP** card on the Scan tab shows your level, EXP per hour, EXP gained, and the time to your next level. It reads the EXP line at the bottom of the game window (`EXP 93,499 [43.17%]`), so keep that line on screen.
   - The first numbers show a few seconds after you press Start. "EXP per hour" shows after a minute.
   - **Reset** starts counting again (for example when you start a new hunting trip).
   - EXP lost from dying is shown apart, not taken off what you gained.
   - To turn it off: Settings > **Track my EXP**.
   - If the card keeps saying "Looking for the EXP line", send Claude a screenshot of the whole game window.

The rest of this guide is the manual way (the zip folder), which still works.

# Step-by-step guide (starting from: Python 3.13 already installed)

Do the steps in order. Do one thing at a time and check that you see what is described before moving on.

**Part A: Install Tesseract**

1. Open your web browser and go to the UB-Mannheim Tesseract page: `https://github.com/UB-Mannheim/tesseract/wiki`.
   - You should see a list of installers. Pick the newest 64-bit one, named like `tesseract-ocr-w64-setup-5.5.3.xxxx.exe`.
   - If you cannot find it: search the web for "UB-Mannheim tesseract" and make sure the address starts with github.com/UB-Mannheim.
2. Click the installer link to download it, then open the downloaded file.
   - You should see a Windows prompt asking whether to allow it. Click Yes.
   - If Windows SmartScreen says "unrecognized app," click More info, then Run anyway, only if you downloaded it from the page in step 1.
3. Click Next through the installer and **keep the default install folder** (`C:\Program Files\Tesseract-OCR`). Leave the default options, including English. Click Install, then Finish.
   - You should see the installer finish with no errors.
   - If it asks about adding to PATH: do not worry, the tool does not need it.
4. Check the install. Press the Windows key, type `cmd`, press Enter. In the black window, paste this exactly and press Enter: `"C:\Program Files\Tesseract-OCR\tesseract.exe" --version`
   - You should see something like `tesseract 5.5.3` and a list of libraries.
   - If you see "The system cannot find the path specified": open File Explorer, go to `C:\Program Files`, and look for a Tesseract-OCR folder. If it is somewhere else, reinstall to the default folder.

**Part B: Unpack the reader**

(Already done this? Your folder is `Desktop\MapleReader`. For updates, see Part I at the end.)

5. Download `MapleReader.zip` from this chat, then open your Downloads folder in File Explorer.
   - You should see `MapleReader.zip`.
6. Right-click `MapleReader.zip`, choose **Extract All...**, click **Browse...**, pick your **Documents** folder, then click **Extract**.
   - You should see a folder `Documents\MapleReader` containing `maple_shop_reader.py`, a `shopreader` folder, a `tests` folder, `setup.bat`, `start.bat`, `test.bat`, `run_tests.bat` and `GUIDE.md`.
   - If you see a folder inside a folder (`MapleReader\MapleReader`), open the inner one; use that one from now on.
7. Don't double-click `maple_shop_reader.py` itself, and don't move files out of the `shopreader` folder: the reader needs it next to `maple_shop_reader.py`. You'll always use the `.bat` files.

**Part C: Install the Python packages**

8. Double-click `setup.bat`. It installs Tesseract for you if it is missing (using Windows' built-in `winget`), then the Python packages.
   - You should see "Already installed." for Tesseract (or an install), then text ending in "Successfully installed" (or "Requirement already satisfied"), then "Done.". Press a key to close.
   - If it says it could not install Tesseract automatically: do Part A by hand.
   - If you see "No suitable Python runtime found" or "'py' is not recognized": Python 3.13 is not installed under the name `py`. Open Command Prompt and type `py list` to see what is installed.
   - If you see a red "ERROR" about the network: check your internet and run setup.bat again.

**Part D: Test on a screenshot**

9. Take a screenshot of an open shop (in the game, press the Windows key + Shift + S, drag around the whole shop window, and save it as a PNG; or use any screenshot you have already).
   - You should see a PNG file saved somewhere you can find, such as Pictures.
   - If you cannot save it: open Paint, press Ctrl+V, then File, Save as, PNG.
10. Drag that screenshot file and drop it onto `test.bat`.
    - You should see a black window showing `room:` and then one line per listing, with the item name, price each and shop name.
    - If it says Tesseract was not found, repeat step 4. The window stays open until you press a key, so you can read any error.
    - If rows are wrong or empty: make sure the screenshot shows the whole shop window at normal game size (not zoomed or shrunk).

**Part E: Game settings**

11. In MapleStory Classic World, set the display mode to **windowed or borderless windowed** (in the game's graphics or display options).
    - You should see the game still running normally, in a window or filling the screen without exclusive fullscreen. This is a precaution and is unverified; exclusive fullscreen commonly gives black screenshots to tools like this.
    - If the scan reads a black screen later: come back to this step and check the mode.

**Part F: Run it while you look at shops**

12. Double-click `start.bat`.
    - You should see a black window starting with `MapleReader 2026-10-20b. Text reading: fast (Tesseract kept in memory).`, then where it is saving, and asking for your channel.
    - If it says `standard (tesseract.exe each time)` instead: everything still works, just slower. Tell Claude, so the fast way can be fixed for your PC.
    - If it says Tesseract was not found: repeat step 4.
13. Open the game's **Change Channel** window once (then press Cancel). The reader reads your channel from the highlighted button.
    - You should see `channel set to 10 (read from the Change Channel window)`.
    - It re-reads it every time you open that window, so changing channel is automatic. You can still type a number in the black window if needed.
14. In the game, go to the Free Market and open shops yourself, one at a time, by clicking them.
    - You should hear a soft two-note chime and see a line like `Saved 6 from "Cheapest NX <3" (room 1, ch 10)`. The chime means you can move on.
    - Sold items (the faded, light rows) are saved too, marked `sold`.
    - If nothing appears after about 10 seconds: make sure the shop window is fully visible and nothing covers it.
15. Scroll the shop list with the **mouse wheel** to see every item. Rows are saved as soon as the list stops moving: scroll down no more than one screenful at a time and let it rest for a moment before the next.
    - The reader follows the scrollbar handle, so a shop full of identical listings (like 14 x "Screw, 1 for 299 mesos") is counted correctly: each row is saved once, and scrolling back up never saves anything twice.
    - Use the wheel rather than dragging the handle or clicking the bar to jump. A jump skips rows the reader never sees; it then counts only what it saw.
16. The room is read from the minimap automatically. Keep the minimap open (it can be anywhere, including a windowed game).
    - You should see the room in each "Saved" line, like `(room 1, ch 10)`.
    - If it shows room 0: check the minimap isn't closed, or type `room 1` (the real number) in the black window. The reader keeps a picture of what it saw in `scans\room_check.png`, which helps Claude fix it.
    - If shop names come out as `Shop`, the reader keeps a picture in `scans\title_check.png` for the same reason.
17. Chime too loud or quiet? Open `start.bat` in Notepad (right-click, Edit) and change the last-but-one line to `py -3.13 maple_shop_reader.py --volume 0.04` (softer) or `--volume 0.2` (louder). Use `--quiet` for no sound at all. Save, then double-click `start.bat` again.
18. When you are finished, close the black window.
    - You should see it stop. Nothing more is saved.

**Part G: Find the scan and use it on the site**

19. Open your market site and click the **Market** tab. The **Import your scans** box is near the top.
    - If you cannot find it: look under the Market tab, not Mine or Items.
20. Click **Choose Files**, open the `scans` folder inside your MapleReader folder and pick **all_scans.txt**. (Or drag `all_scans.txt` from the folder and drop it anywhere on the site.)
    - You should see `Imported 29 new rows.` (your number) and the listings appear below.
    - Always import this same file. It holds everything the reader ever saved, and the site only adds the rows it has not seen, so you never need to work out which file is new. `Nothing new: every row was already imported.` just means you are up to date.
    - Each session also gets its own file, like `scan_2026-10-19_1530.txt`. You don't need those for the site; they are a backup.
21. What the site does with the rows:
    - It uses the time each row was seen, so "seen 2 h ago" and the Time of day tiles are right even if you import later.
    - A listing counts as **gone** only when you reopen that same shop later and it is no longer there. Shops you did not reopen keep their listings as for sale.
    - Rows a few minutes apart count as one scanning session, so importing in the middle of a session and again at the end is fine.
22. Before trusting Deals, open one real shop in-game and compare one multi-item listing with what the site shows, to confirm that "price each" matches the in-game price.
    - You should see the same price per item.
    - If the site's price looks like the whole bundle price: note this and treat Deals as unreliable until fixed.

**Part G2: The MapleReader app (scanner and market in one window)**

The app is one window with four tabs:

| Tab | What it's for |
|---|---|
| **Scan** | The **Start watching** button, your channel and room, and every listing as it's saved, with its picture |
| **Prices** | One row per item you've scanned: the cheapest price on sale now, how many are for sale, and when it was last seen. Click an item to see **where to buy it**, cheapest first |
| **Listings** | Every shop listing, newest or cheapest first. Two identical copies in one shop show once, as "×2" |
| **More** | Alerts and deals, your own shop's listings, where prices come from, and importing older scan files |

Listings you scan show up in Prices and Listings by themselves, with no importing.

A. Make `MapleReader.exe` (once, and again after each update):
   1. Double-click `build_exe.bat`. It installs the build tools, builds the app, and puts `MapleReader.exe` and an `_internal` folder in your MapleReader folder. It takes 2 to 5 minutes.
   - You should see `Done. Double-click MapleReader.exe to start.`
   - Keep `_internal` next to `MapleReader.exe`. For a desktop icon, right-click the exe, **Send to > Desktop (create shortcut)**.
   - If your antivirus warns about the new exe: home-made exes are sometimes flagged because they aren't signed. It was built on your PC from the files in this folder. `start_app.bat` opens the same app without an exe.
B. Use it:
   1. Double-click `MapleReader.exe`.
      - You should see a window open on the **Scan** tab, with three numbered steps. It starts watching by itself, so step 1 already has a green tick and the top right says `Scanning`. (It uses the Edge browser that comes with Windows, without the address bar, so it looks like an app.)
      - If the big button says **Install Tesseract**: click it, click **Yes** if Windows asks, and wait about a minute. When the black window says `Done`, close it. The button changes to **Start watching** by itself; click it.
   2. If it isn't watching yet (the big yellow button says **Start watching**), click it.
      - You should see step 1 get a green tick, and the top right say `Scanning`.
   3. In the game, open the Change Channel window once, then close it.
      - You should see step 2 get a tick and your channel appear under **Channel**.
      - If it doesn't: click **Change** under Channel, type the channel number, and click **Save**.
   4. Open shops in the Free Market as usual.
      - You should hear a soft chime and see each listing appear on the right with its picture. New ones say **just listed** in green for a few minutes. The steps go away once the first listing is saved.
      - If the room shows `—`: check the minimap is open, or click **Change** under Room and type it.
   5. To look up a price, click **Prices**, type part of the name (for example `scroll`), and click the item. (Shortcut: press `/` to jump to the search box, `Esc` to go back.)
      - You should see the cheapest price now, the usual price, and a **Where to buy** list with the shop, room (FM) and channel (CH).
      - To be told when it gets cheaper: under **Price alert**, type the most you'd pay and click **Tell me when it's this price or less**. You'll hear a chime when a scan finds one.
      - **Listings** shows what was seen in the last 3 days; the button at the bottom shows older ones.
   6. When you're done, click **Stop**, or just close the window (closing it closes MapleReader).
   - **Settings** (on the Scan tab; click it to open): start watching when MapleReader opens (on unless you switch it off), chime on or off and its volume, the screen the game is on, **Test a screenshot** to check a saved picture, and **Open scans folder**.
   - Pictures are cut from the shop window the first time each item is seen, and kept in `scans\icons`.
   - The first time, the app reads all of `all_scans.txt`, so everything you scanned before is there. **More > Older scan files > Reload all** clears it and reads the file again.
   - The copy of the market on Claude still works, but it doesn't update by itself and has no pictures: there you import `all_scans.txt` as before (Part G).
   - Using `start.bat` instead? Double-click `market.bat` to open the live market in your browser.

**Part G3: Share with friends (the group market): paused**

The group market (a shared website for you and your friends) is paused for now, so MapleReader keeps everything on your PC and the sharing settings are hidden. When it's set up later (`maple-server\SETUP.md`), the steps to turn it on will be here.

**Part H: Check the reader still works (after an update)**

23. Double-click `run_tests.bat`.
    - It reads the saved test pictures in `tests\fixtures` and plays a pretend game session through the reader. It takes a few minutes.
    - You should see `ALL PICTURE CHECKS PASSED`, `SESSION CHECK PASSED`, then `Everything passed.`
    - If something failed: copy the text in the window and send it to Claude.

**Part I: Installing an update**

24. Download `MapleReader-update.zip`, right-click it, choose **Extract All...**, and extract it to your **Desktop** (the folder that contains `MapleReader`).
    - When Windows asks, choose **Replace the files in the destination**.
    - An update only contains the files that changed; everything else (your `scans` folder, `items.txt`) is left alone.
25. Double-click `run_tests.bat` to check the update (Part H).

**What's in the folder**

| File | What it does |
|---|---|
| `MapleReader.exe` | The app: scanner and market in one window (after running `build_exe.bat`) |
| `start_app.bat` | Opens the same app window without building the exe |
| `build_exe.bat` | Builds `MapleReader.exe` (it runs `build_app.py`) |
| `installer\MapleReader.iss` | How the installer is made (the automatic build on GitHub uses it) |
| `start.bat` | Starts watching the screen in the black window |
| `market.bat` | Opens the live market without the app (for `start.bat` users) |
| `test.bat` | Reads one screenshot you drop on it |
| `run_tests.bat` | Checks everything still works |
| `setup.bat` | Installs the Python packages (once) |
| `maple_shop_reader.py` | Starts the reader (the work is in `shopreader`) |
| `shopreader\config.py` | Every number you might tune: colours, timings, volume |
| `shopreader\*.py` | The parts: finding the list, reading rows, names, room and channel, chime, the watching loop |
| `tests\` | Test pictures and the checks run by `run_tests.bat` |
| `scans\` | Your saved scan files |

**Troubleshooting**

| Problem | What it usually means | What to do |
|---|---|---|
| Tesseract not found | Not installed, or installed in a different folder | Repeat step 4; reinstall to the default folder |
| `'py' is not recognized` | Python install manager not set up | Open Command Prompt, type `py list`; reinstall Python 3.13 |
| Pip errors in setup.bat | Network or permissions problem | Check internet; run setup.bat again |
| Files missing or won't run | Zip not extracted, or run from inside the zip | Extract All first (step 6) |
| Black or blank screenshots | Game in exclusive fullscreen | Use windowed or borderless windowed (step 11) |
| Wrong item names | Small text misread | Add an items.txt list so names get corrected |
| Wrong room | Room not read from the minimap | Type `room 9` with the right number (step 16) |
| Item or shop names come out garbled ("Biue yyaIcn") after you resize the game or change its resolution | The game draws its shop text at a different size, and the "Filter Applied" setting blurs it | MapleReader now adjusts to the new size by itself. For the clearest reading: game **Options > Graphics > UI Size**: choose **Default Ratio** or **Ideal Ratio** (not "Filter Applied") |
| Wrong channel | Change Channel window not opened since you switched | Open it once, or type the number |
| `No module named shopreader` | `shopreader` folder missing or moved | Extract the full zip again so `shopreader` sits next to `maple_shop_reader.py` |
| Rows missed when scrolling | You dragged the handle or jumped down the list | Scroll with the mouse wheel (step 15) |
| Chime too loud | Default volume | Use `--volume 0.04` or `--quiet` (step 17) |
| Reader crashes or closes as soon as it reads a shop | The fast way of running Tesseract does not suit your PC | Edit `start.bat` so the reader line ends in `--slow-ocr`, and tell Claude |
| Site says "Nothing new" | You already imported every row | Scan more shops, then import `all_scans.txt` again |
| Top right says "MapleReader closed" | The app (or `market.bat`) was closed | Start it again; the page catches up by itself |
| Sharing says it can't reach the market | No internet, or the server is down | Nothing to do: your scans are kept and sent when it's back |
| No pictures next to items | They are cut from shops you open | Open the shop once with the app running; older items get pictures as you see them again |
| Live market is empty after opening it in a different browser | Each browser keeps its own copy | Use one browser, or click **Reload all** to read everything again |
| Nothing saved | Shop window not fully visible, or screen unchanged | Move other windows away; wait a few seconds |
| Slow reads | Modest CPU | Wait; do not open shops faster than it reads |

**Reminder:** nothing here has been confirmed as allowed by Nexon. Read Nexon's current Terms of Use, Rules of Conduct and the MapleStory Classic support pages yourself before you use the tool, and use it at your own risk.
