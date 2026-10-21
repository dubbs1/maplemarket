# Maple Classic Market

Know what things cost in the Free Market, without walking every room.

**MapleReader** is a small Windows app. While you browse shops as usual, it reads each shop window on your screen and keeps every listing: item, price, shop, room, channel, sold or not, and the item's picture. Then it shows you prices, trends, where to buy, and your EXP per hour — on your PC, and (if you share) on a website your friends can open on their phones.

It only takes screenshots and reads the text in them. It never clicks, types, reads the game's memory or touches its network traffic.

## Get started

1. Open the **Releases** page (on the right) and download `MapleReader-Setup-<version>.exe`.
2. Double-click it. Click **Yes** if Windows asks.
   - You should see a MapleReader icon on your desktop, and the app opens by itself.
3. The first time, press the big button to install **Tesseract** (the free program that reads text). Click **Yes** if Windows asks, then wait for "Done".
4. Play. Open the Change Channel window once (so the app knows your channel), keep the minimap open (so it knows your room), and open shops as you normally would.
   - You should hear a soft chime each time a shop's listings are saved.

Full instructions, with "You should see…" at every step, are in [`MapleReader/GUIDE.md`](MapleReader/GUIDE.md).

## What you get

| Tab | What it shows |
|---|---|
| **Home** | Search any item, today's numbers, what was just listed, and your price alerts |
| **Prices** | Every item you've seen, cheapest for sale now, usual price, and a price history chart |
| **Listings** | Every listing by kind of item: for sale, sold, newest, best deal, with the shop, room and channel |
| **EXP** | EXP per hour, the last 5 minutes, time to level, mesos per hour, and a log of your hunting runs |
| **Options** | Sound, dark theme, sharing with friends, and the settings |

## Share with friends

Everyone who scans sees everyone's listings. The group market is a website (`maple-cloud/`) that runs on Vercel and Supabase for free: each friend gets a personal key, puts it in **Options › Share with friends**, and their scans flow to the site. Phones work too (open the site, then "Add to Home Screen"). Setting it up takes about 20 minutes: [`maple-cloud/SETUP.md`](maple-cloud/SETUP.md).

## Privacy and rules

- Everything stays on your PC unless you turn sharing on. Then only the scan lines and item pictures are sent, with your key.
- No game files are read or changed. Nexon has not said whether screen readers are allowed; use at your own judgement.
- Prices come only from what you and your friends see. Nothing is copied from other sites.

## For developers

- `MapleReader/` — the app (Python 3.13). `shopreader/` holds the parts: finding the shop list, reading rows, scrolling, room and channel, EXP, pictures, the local server and the sharing uploader. `tests/` checks it against real screenshots (`run_tests.bat`).
- `maple-cloud/` — the group market: one Vercel function, a Supabase schema, the page.
- `maple-server/` — the same group market for a server of your own (Python + SQLite).
- `dev-tests/` — page checks (`npm test`), browser end-to-end runs, the install-script check. `bash dev-tests/run_all.sh` runs everything.
- [`CLAUDE.md`](CLAUDE.md) — how it all fits together and the decisions behind it.
