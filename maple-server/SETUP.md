# Putting the group market online

The group market gets **its own DigitalOcean droplet** (a small rented server, about $6 a month). Nothing else runs on it, so it can't get in the way of Rev Market or any other project, and Rev Market's droplet is never logged in to.

You'll do four things, in order:

1. Make the droplet (10 minutes).
2. Point the address `maple.vendormarket.app` at it (5 minutes, then a short wait).
3. Install the market with one command (5 minutes).
4. Make keys for yourself and your friends (1 minute each).

Each step says what you should see. If you see something else, stop and send Claude a screenshot or the window's text.

---

## Part 1: Make the droplet

1. Open <https://cloud.digitalocean.com> and log in (the same account as Rev Market is fine).
   - You should see your projects, with Rev Market's droplet in the list.
2. Click the green **Create** button at the top right, then **Droplets**.
   - You should see "Create Droplets".
3. **Region:** pick the one closest to you and your friends (for example New York or San Francisco).
4. **Choose an image:** click **Ubuntu**, then pick **24.04 (LTS) x64** in the version list.
5. **Choose Size:** click **Basic**, then **Regular**, then the **$6/mo** box (1 GB memory).
   - The $4 box works too, but 1 GB leaves more room.
6. **Choose Authentication Method:**
   - If you see **SSH Key** with a key already listed (the one you use for Rev Market), click **SSH Key** and tick that key.
   - If no key is listed, click **Password** and type a strong password. Write it down: you'll type it each time you send an update.
7. **Hostname:** type `maple-market`.
8. Click **Create Droplet** at the bottom.
   - You should see the new droplet with a progress bar, then an address like `203.0.113.7` under **ipv4**.
   - If it says the account has reached its droplet limit, send Claude a screenshot.
9. Click the address once to copy it, and paste it somewhere safe (Notepad). Below it's called **the droplet's IP**.
10. Check that you can log in. Press the Windows key, type `powershell` and press Enter. In the blue window type (with your IP):
    ```
    ssh root@203.0.113.7
    ```
    - The first time it asks `Are you sure you want to continue connecting?`: type `yes` and press Enter.
    - If you chose a password, type it (nothing shows while you type) and press Enter.
    - You should see a line ending in `root@maple-market:~#`. Type `exit` and press Enter.
    - If it says `Connection refused` or `timed out`, wait 2 minutes (the droplet is still starting) and try again.
    - If it says `Permission denied`, the key or password didn't match. Send Claude the text.

## Part 2: Point `maple.vendormarket.app` at the droplet

The name costs nothing: it's a sub-name of the domain you already own. You add it where `vendormarket.app`'s DNS records live. That's one of these places:

- **Cloudflare** (if you log in to Cloudflare to manage vendormarket.app): Websites → vendormarket.app → **DNS** → **Records**.
- **DigitalOcean**: left menu **Networking** → **Domains** → vendormarket.app.
- **Where you bought the domain**: its "DNS" or "Manage DNS" page.

1. Open that page.
   - You should see a list of records, including one for `vendormarket.app` (Rev Market). **Leave every existing record exactly as it is.**
2. If there's already a record named `maple`, click **Edit** on it. Otherwise click **Add record**.
3. Fill in:

   | Type | Name | Value (IPv4 address) |
   |---|---|---|
   | A | `maple` | the droplet's IP from Part 1 |

   - **On Cloudflare:** click the orange cloud so it turns **grey ("DNS only")**. Your droplet makes its own HTTPS certificate, and that works best with the grey cloud.
4. Click **Save**.
5. Wait 5 minutes. Then in PowerShell type:
   ```
   nslookup maple.vendormarket.app
   ```
   - You should see the droplet's IP near the bottom (after `Addresses:` or `Address:`).
   - If you see a different address, or `Non-existent domain`, wait 10 more minutes and try again.

## Part 3: Install the market

1. Extract `maple-server.zip` somewhere on your PC (for example your Desktop), or use the `maple-server` folder from git.
2. Open the `maple-server` folder, click the address bar at the top, type `powershell` and press Enter.
   - You should see a PowerShell window whose last line ends in `maple-server>`.
3. First, only look (this changes nothing). Paste this and press Enter:
   ```
   powershell -ExecutionPolicy Bypass -File deploy-maple.ps1 -Check
   ```
   - It asks `Which droplet?`. Type `root@` and the droplet's IP, for example `root@203.0.113.7`, and press Enter. It remembers this for next time.
   - Type the password if you chose one.
   - You should see `OK` lines, including `nothing serves websites here yet: nginx and an HTTPS certificate will be set up just for Maple`, and finally `Check only: nothing was changed.`
   - If you see **STOPPED**, send Claude the window's text.
4. Now install. Paste this (put your own email in; it's only used for "your certificate is expiring" notices, which normally never come) and press Enter:
   ```
   powershell -ExecutionPolicy Bypass -File deploy-maple.ps1 -Email you@example.com
   ```
   - It takes 2 to 5 minutes. You should see sections 1 to 3 with `OK` lines, `HTTPS certificate for maple.vendormarket.app`, and finally `All done.`
   - If it says it **couldn't get the HTTPS certificate yet**, the address from Part 2 isn't ready. Wait 10 minutes and run the same command again; it's safe to repeat.
   - If it still fails after an hour, send Claude the window's text and the file `/tmp/maple-certbot.log` on the droplet.
5. Open <https://maple.vendormarket.app> in your browser.
   - You should see the market page with a **Shared market** chip at the top right.

## Part 4: Make keys

Each person who scans gets their own key. Nobody needs a key just to look.

1. In PowerShell, log in to the droplet: `ssh root@203.0.113.7` (your IP).
2. Make your own key (use your name):
   ```
   sudo -u maple python3 /home/maple/maple-market/manage.py add Cass
   ```
   - You should see `Key for Cass:  mm-…`. Copy it now: it's shown only once.
3. Make one for each friend: `... add Gunther`, `... add JJ`, and so on. Send each their key privately.
4. Other commands (same start, `sudo -u maple python3 /home/maple/maple-market/manage.py`):
   - `list`: who has a key.
   - `revoke Gunther`: their key stops working at once.
   - `restore Gunther`: it works again.
   - `add Gunther` after a revoke: gives them a fresh key.
   - `purge Gunther`: deletes everything they sent.
   - `stats`: how much each person has sent.
5. Type `exit` to log out.

## Part 5: Turn sharing on in MapleReader

In MapleReader, **Scanner** tab → **Share with friends**:

1. Market address: `https://maple.vendormarket.app` (already filled in).
2. Your key: paste the `mm-…` key, then click **Save**.
   - You should see `Sharing as Cass · N sent`. Everything you've scanned so far is sent once; after that each new listing goes within a few seconds.
   - Your **Market** tab now also shows friends' listings and pictures. The top right says how many friends are scanning.
   - Offline, or the server's down? Your scans are kept and sent later; nothing is lost.

Give each friend the full MapleReader zip (with its `GUIDE.md`), their key, and the address `https://maple.vendormarket.app`. Anyone can look at the market in a browser, phone included.

---

## Later

All of these run in PowerShell from the `maple-server` folder (it remembers the droplet):

| To… | Run |
|---|---|
| Update the market after Claude sends new files | `powershell -ExecutionPolicy Bypass -File deploy-maple.ps1` (data and keys are kept) |
| Only look at the droplet | `powershell -ExecutionPolicy Bypass -File deploy-maple.ps1 -Check` |
| Take the site down (keeps the data) | `powershell -ExecutionPolicy Bypass -File deploy-maple.ps1 -Remove` |
| Copy all the data to your PC | `scp -r root@203.0.113.7:/home/maple/maple-market/data maple-backup` |

On the droplet (`ssh root@…` first):

| To… | Run |
|---|---|
| See if it's running | `systemctl status maple-market` (look for `active (running)`) |
| See its log | `journalctl -u maple-market -n 50 --no-pager` |
| Restart it | `systemctl restart maple-market` |

- **Automatic backups (optional):** in DigitalOcean, open the droplet → **Backups** → **Enable**. It costs about 20% of the droplet's price.
- **A different address:** add `-Domain market.example.com` to the install command (and make the DNS record for that name instead).

## On the same droplet as Rev Market instead (not recommended)

It also works next to Rev Market without touching it: its own user, folder, settings and service, and **one new entry** in the web front door (nginx or Caddy), checked first and taken back out if refused. Rev Market's files and service are never edited. Use `-Server root@vendormarket.app` on the commands above, and point the `maple` DNS record at Rev Market's IP. A droplet of its own keeps the two projects fully apart, which is why it's the main way.

## Good to know

- Two friends scanning the same shop count it once.
- A listing someone scans shows on everyone's page within a few seconds, with the right "just listed" time even if friends live in other time zones.
- Each viewer's browser keeps the last 30 days. **Market → This market → Reload all** reads everything again.
- Each person runs the screen reader on their own account. Like you, they accept that Nexon hasn't confirmed screen readers are allowed.
