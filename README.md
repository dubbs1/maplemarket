# Maple Classic Market

Know what things cost in the Free Market, without walking every room.

**MapleReader** is a small Windows app. While you browse shops as usual, it reads each shop window on your screen and remembers every listing: the item, its price, the shop, the room and channel, and whether it sold. Then it shows you prices, what's trending, where to buy, and your EXP per hour.

It only looks at your screen. It never clicks, types, or touches the game.

## Install

1. Open **Releases** (on the right) and download `MapleReader-Setup-<version>.exe`.
2. Double-click it. Click **Yes** if Windows asks.
3. The first time, press the big button to install **Tesseract**, the free program that reads text. Click **Yes** if Windows asks, then wait for "Done".

That's it. The app opens by itself and starts watching.

## Use it

- Open the **Change Channel** window once, so the app knows your channel.
- Keep the **minimap** open, so it knows your room.
- Open shops as you normally would. A soft chime means the listings were saved.

| Tab | What it shows |
|---|---|
| **Home** | Search any item, today's numbers, just listed, your price alerts |
| **Prices** | Every item you've seen: cheapest now, usual price, price history |
| **Listings** | Every listing, with the shop, room and channel to find it |
| **EXP** | EXP per hour, time to level, mesos per hour, kills by mob, damage taken, a log of your hunts |
| **Options** | Sound, EXP recording, updates, sharing with friends (the Theme button in the header switches day and night) |

The step-by-step guide, with pictures of what you should see, is in [the Guide](MapleReader/GUIDE.md).

## Share with friends

Turn on **Options › Share with friends** and your scans go to a shared market page that everyone in your group can open, on a phone too. Each friend gets their own key. Setting up the shared page is free and takes about 20 minutes: [Setup](maple-cloud/SETUP.md).

## Good to know

- Everything stays on your PC unless you turn sharing on.
- No game files are read or changed. Whether screen readers are allowed is for Nexon to say; use your own judgement.
- Prices come only from what you and your friends have seen. Nothing is copied from other sites.

---

Developers: the app is in `MapleReader/`, the shared market in `maple-cloud/`, and the notes on how it all fits together in [CLAUDE.md](CLAUDE.md).
