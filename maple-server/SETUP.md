# Putting the group market on maple.vendormarket.app

This sets up the shared Maple market on the same DigitalOcean server as Rev Market, **completely separate from it**: its own folder (`/home/maple/maple-market`), its own user, settings file (`/etc/maple-market.env`), service (`maple-market`) and database. Rev Market's files are never edited. The only shared piece is the web "front door" (nginx or Caddy), which gets **one new entry** for `maple.vendormarket.app`; it's backed up and checked first, and put back if anything is wrong.

Do the steps in order. Each one says what you should see.

---

## Step 0: Look before changing anything (2 minutes)

1. Extract `maple-server.zip` somewhere on your PC, for example your Desktop.
2. Open the `maple-server` folder, click the address bar, type `powershell` and press Enter.
3. Paste this and press Enter:
   ```
   powershell -ExecutionPolicy Bypass -File deploy-maple.ps1 -Check
   ```
   - You should see it log in to `root@vendormarket.app` (the same login you use for Rev Market), then lines like `OK  python3 3.12` and `OK  web front door: nginx`.
   - **Nothing is changed** in this step.
   - If the front door says `none`, or anything stops with **STOPPED**, send Claude the window's text before going on.

## Step A: Add the address `maple` (5 minutes, then a short wait)

The name `maple.vendormarket.app` costs nothing: it's a sub-name of the domain you already own. You add it where `vendormarket.app`'s DNS records are kept, which is one of these:

- **Cloudflare** (if you log in to Cloudflare to manage vendormarket.app): Websites → vendormarket.app → DNS → Records → **Add record**.
- **DigitalOcean**: Networking → Domains → vendormarket.app.
- **Where you bought the domain**: its "DNS" or "Manage DNS" page.

Add:

| Type | Name | Value |
|---|---|---|
| A | `maple` | the same IP address as the existing `vendormarket.app` record (or your droplet's IPv4 from the DigitalOcean dashboard) |

- On Cloudflare, leave the cloud orange (Proxied), the same as your `vendormarket.app` record.
- **If step 0 said `cloudflare tunnel`**, don't add an A record. Instead: Cloudflare → Zero Trust → Networks → Tunnels → your tunnel → **Public hostname → Add**. Subdomain `maple`, domain `vendormarket.app`, service type `HTTP`, URL `127.0.0.1:8790` (step B prints the exact address).
- Wait about 5 minutes before step B.

## Step B: Install it (2 minutes)

In the same PowerShell window:
```
powershell -ExecutionPolicy Bypass -File deploy-maple.ps1
```
- You should see sections 1 to 3 with `OK` lines, ending with `Done.`
- `HTTPS certificate for maple.vendormarket.app` means it's ready.
- If it says it couldn't get the certificate, the address from step A isn't ready yet. Wait 10 minutes and run the same command again; it's safe to repeat.
  If it still fails after an hour, send Claude the window's text and the file `/tmp/maple-certbot.log` (Cloudflare's SSL setting can need one change).
- Open `https://maple.vendormarket.app` in your browser. You should see the market with a "Shared market" chip at the top right.

## Step C: Make keys (1 minute per person)

Each person who scans gets their own key; nobody needs a key just to look. Log in to the server as you do for Rev Market (`ssh root@vendormarket.app`) and run:
```
sudo -u maple python3 /home/maple/maple-market/manage.py add Cass
```
- You should see `Key for Cass:  mm-…`. Copy it; it's shown only once.
- Make one per friend: `... add Gunther`, `... add JJ`, and so on. Send each their key privately.
- Other commands:
  - `... list`: who has a key.
  - `... revoke Gunther`: their key stops working at once.
  - `... restore Gunther`: it works again.
  - `... purge Gunther`: deletes everything they sent.
  - `... stats`: how much each person has sent.

## Step D: Turn sharing on in MapleReader

In MapleReader, **Scanner** tab → **Share with friends**:
1. Market address: `https://maple.vendormarket.app` (already filled in).
2. Your key: paste the `mm-…` key, then click **Save**.
- You should see `Sharing as Cass · N sent`. Everything you've scanned so far is sent once; after that, each new listing goes within a few seconds.
- Your **Market** tab now also shows your friends' listings and pictures. The top right says how many friends are scanning.
- Offline, or the server's down? Your scans are kept and sent later; nothing is lost.

## Friends

Give each friend:
1. the full MapleReader zip, with its `GUIDE.md` steps (Tesseract, `setup.bat`, `build_exe.bat`);
2. their key, and the address `https://maple.vendormarket.app`.

Anyone can just look at the market in a browser, phone included, at `https://maple.vendormarket.app`.

## Later

- **Update the market:** extract the new `maple-server.zip` and run step B again. Your data and keys are kept.
- **Is it running?** `systemctl status maple-market` (look for `active (running)`).
- **Its log:** `journalctl -u maple-market -n 50 --no-pager`.
- **Restart only Maple:** `systemctl restart maple-market` (Rev Market keeps running).
- **Take the Maple site down:** `systemctl disable --now maple-market`, then remove `/etc/nginx/sites-enabled/maple-market` and run `systemctl reload nginx`. Rev Market isn't affected.

## Good to know

- Two friends scanning the same shop count it once.
- A listing someone scans shows on everyone's page within a few seconds.
- Each viewer's browser keeps the last 30 days. **Market → This market → Reload all** reads everything again.
- Each person runs the screen reader on their own account. Like you, they accept that Nexon hasn't confirmed screen readers are allowed.
