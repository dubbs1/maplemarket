# Setting up the group market on Vercel + Supabase

This puts the group market at **https://maple.vendormarket.app**, free, with no server to look after:

- **Supabase** keeps the listings, the item pictures and the friends' keys.
- **Vercel** runs the website (the market page and the small program MapleReader sends listings to).
- Your MapleReader still does all the scanning, on your PC. Phones only look.

Rev Market is not touched. The only shared thing is one new DNS record, `maple`, under vendormarket.app.

You need about 30 minutes. Do the parts in order. Keep a Notepad window open to paste things into.

---

## Part 1: Supabase (the database)

1. Go to **https://supabase.com** and click **Start your project**. Choose **Continue with GitHub** and sign in with the same GitHub account the code is on.
   - You should see your Supabase dashboard.
2. Click **New project**.
   - **Name:** `maple-market`
   - **Database password:** click **Generate a password**, then copy it into Notepad. (You won't need it day to day, but keep it.)
   - **Region:** **East US** (or the one closest to you and your friends).
   - Click **Create new project**.
   - You should see "Setting up project". Wait until it finishes (about 2 minutes).
3. On the left, click **SQL Editor**, then **New query** (or the **+**).
4. Open the file `maple-cloud/schema.sql` on GitHub (in the maplemarket repository), click the **Copy raw file** button (two squares), and paste it all into the SQL Editor. Click **Run** (bottom right).
   - You should see **Success. No rows returned**.
   - If you see a red error instead, take a screenshot of it and send it to me.
5. On the left, click **Storage**.
   - You should see a bucket called **icons**, marked **Public**.
   - If there's no `icons` bucket: click **New bucket**, name it `icons`, turn **Public bucket** on, and click **Save**.
6. Get the two values the website needs. On the left, click the **gear** (Project Settings).
   - Under **Data API** (or **API**), copy the **Project URL** (it looks like `https://abcdefgh.supabase.co`) into Notepad.
   - Under **API Keys**, find **Secret keys** and copy the secret key (it starts with `sb_secret_`). You may need to click **Reveal** first.
   - If you only see **Legacy API keys**, copy the **service_role** key instead.
   - **Keep this key secret.** Never post it, send it or screenshot it. Anyone with it can change the market.

## Part 2: Vercel (the website)

1. Go to **https://vercel.com** and click **Sign Up**. Choose **Hobby**, type your name, then **Continue with GitHub**.
   - You should see your Vercel dashboard.
2. Click **Add New…** then **Project**.
3. Under **Import Git Repository**, find **maplemarket** and click **Import**.
   - If you don't see it: click **Adjust GitHub App Permissions**, allow Vercel to see the **maplemarket** repository, and come back.
4. On the **Configure Project** page:
   - **Root Directory:** click **Edit**, choose **maple-cloud**, click **Continue**.
   - **Framework Preset:** **Other**.
   - Open **Environment Variables** and add two (type the name on the left, paste the value on the right, click **Add** each time):
     - `SUPABASE_URL` = the Project URL from Part 1
     - `SUPABASE_SECRET_KEY` = the secret key from Part 1
5. Click **Deploy**.
   - You should see "Congratulations!" after about a minute.
6. Click **Continue to Dashboard**, then **Visit**.
   - You should see the market page, empty for now ("Nothing yet. Listings appear here as friends scan.").
7. Check the connection: add `/api/rows?from=0` to the end of that address and press Enter.
   - You should see a short line of text starting with `{"text": ""`.
8. Check that the address carries its question: change the end to `/api/rows?from=99999` and press Enter.
   - You should see `"reset": true` somewhere in the line. (If it says `"reset": false`, send Claude the exact line: the `from=` part didn't arrive, and the market would re-read everything on every look.)
   - If it says **not set up yet**: a setting from step 4 is missing. In Vercel, open the project, **Settings** › **Environment Variables**, fix it, then **Deployments**, the **⋯** next to the newest one, **Redeploy**.
   - If it says **said no**: schema.sql didn't run. Do Part 1 step 4 again.

## Part 3: Your address (maple.vendormarket.app)

1. In Vercel, open the project, then **Settings** › **Domains**. Type `maple.vendormarket.app` and click **Add**.
   - You should see it marked **Invalid Configuration**, with a **CNAME** record to add: name `maple`, and a value like `cname.vercel-dns.com` (copy exactly what it shows).
2. Go to where vendormarket.app's DNS is managed. If that's DigitalOcean: **Networking** › **Domains** › **vendormarket.app**. (DNS keeps working while the droplets are off.)
3. Add the record: type **CNAME**, hostname `maple`, "is an alias of" the value from Vercel. Leave the rest as it is, and click **Create Record**.
   - **Don't change or delete any other record.** Rev Market uses them.
4. Back in Vercel's **Domains** page, wait until `maple.vendormarket.app` says **Valid Configuration** (from a few minutes up to an hour). The secure certificate (https) is made for you.
   - You should see the market at **https://maple.vendormarket.app**.

## Part 4: Keys for you and your friends

Each person who scans needs their own key. Looking needs no key.

1. In Supabase, click **SQL Editor**, then **New query**. Type this (with the person's name) and click **Run**:
   ```
   select maple_add_key('YourName');
   ```
   - You should see one result starting with `mm-`. Copy it. It is shown only this once (only a scrambled copy is kept).
   - Send each friend their key privately (not in a public channel).
2. Other things you can run the same way:
   ```
   select * from maple_people;          -- who has a key
   select maple_revoke('Gunther');      -- stop their key working
   select maple_restore('Gunther');     -- let their newest key work again
   select maple_purge('Gunther');       -- delete every listing they sent
   select * from maple_stats;           -- listings per person
   ```

## Part 5: Turn sharing on in MapleReader

Do this on every PC that scans, once its MapleReader is version **2026-10-21b** or newer.

1. In MapleReader, click **Options**, then find the **Share with friends** card.
2. **Market address:** `https://maple.vendormarket.app` (or the `….vercel.app` address from Part 2, until Part 3 is done).
3. **Your key:** paste your `mm-…` key. Click **Save**.
   - You should see **Sharing as YourName · … sent**.
   - If it says **Key not accepted**: check the key was copied whole, with no space at the end.
4. On your phone, open **https://maple.vendormarket.app**.
   - You should see your listings (and your friends') within a minute.

## Good to know

- **Free plans.** Supabase pauses a free project after about a week with no activity (nobody scanning). If the market stops answering after a quiet week, log in to Supabase and click **Restore project**. Vercel's free Hobby plan is for non-commercial use, which this is.
- **Updates come by themselves.** Whenever a change to the market page is merged on GitHub, Vercel rebuilds the site within a minute or two.
- **Space.** Listings older than 35 days are deleted by themselves, and at most 20,000 item pictures are kept, so the free storage is plenty.
- **EXP isn't shared yet.** The phone shows the market; your EXP stays in the app on your PC.
