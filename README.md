# Maple Classic Market

Free Market prices for MapleStory Classic, collected from your own screen while you browse shops.

- **MapleReader** (`MapleReader/`): a Windows app that watches the shop windows you open, reads every listing (item, price, shop, sold or not, room, channel, item picture) and keeps them. It only takes screenshots and reads them. It never clicks, types, reads game memory or touches the network traffic.
- **Market page**: the clean market view with Scanner, Market, Mine, Items, Deals and Sources tabs, shown inside the app.
- **Group market** (`maple-server/`): an optional shared server (`maple.vendormarket.app`) on a DigitalOcean droplet of its own. Friends' apps send their scans to it, and everyone sees everyone's listings.

## Start here

| I want to… | Read |
|---|---|
| Install and use MapleReader on Windows | the installer from **Releases**, or [`MapleReader/GUIDE.md`](MapleReader/GUIDE.md) |
| Put the group market online (its own DigitalOcean droplet) | [`maple-server/SETUP.md`](maple-server/SETUP.md) |
| Work on the code (or have Claude Code work on it) | [`CLAUDE.md`](CLAUDE.md) |

## Folders

```
MapleReader/          the Windows app (Python 3.13)
  app.py              starts the app window (MapleReader.exe after build_exe.bat)
  maple_shop_reader.py  the black-window version (start.bat)
  shopreader/         the parts: reading shops, scrolling, room/channel, pictures, app server, sharing
  tests/              checks with real screenshots (run_tests.bat)
maple-server/         the group market server (plain Python + SQLite) and its setup scripts
dev-tests/            extra checks for development (market page, browser end-to-end, install script)
tools/                small helpers (keeping the two market.html copies the same)
```

## Checks

- **Windows:** double-click `MapleReader\run_tests.bat`.
- **Market page:** `npm install`, then `npm test`.
- **Group server:** `python3 maple-server/tests/test_server.py`.
- **More (browser end-to-end, install script):** see the Checks table in [`CLAUDE.md`](CLAUDE.md).
