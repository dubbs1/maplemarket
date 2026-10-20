#!/usr/bin/env bash
# Installs or updates the Maple market. It stands on its own: its own user, folder, settings file,
# service and web address, so it never mixes with other projects.
#   bash install.sh            install / update (safe to run again)
#   bash install.sh --check    only look around and report; changes nothing
#   bash install.sh --remove   take the Maple site down; its data stays in /home/maple/maple-market/data
# Settings (optional):  MAPLE_DOMAIN  the web address (default maple.vendormarket.app)
#                       MAPLE_EMAIL   email for HTTPS certificate notices
#
# Two kinds of server:
#   a droplet of its own (nothing serving websites yet): nginx and a free HTTPS certificate are set up for Maple.
#   a server that already runs other sites: ONE new entry for the Maple address is added to the web
#     front door they use (nginx or Caddy), checked first and taken back out if refused.
# What it touches:   /home/maple/maple-market (code + data), /etc/maple-market.env,
#                    /etc/systemd/system/maple-market.service, and that one front-door entry.
# What it never touches: other sites' entries, files or services (Rev Market: /home/market,
#                        (its own folder), (its own settings file)).
set -euo pipefail

DOMAIN="${MAPLE_DOMAIN:-maple.vendormarket.app}"
EMAIL="${MAPLE_EMAIL:-}"
APP=/home/maple/maple-market
ENVF=/etc/maple-market.env
UNIT=/etc/systemd/system/maple-market.service
MARK="# Maple Classic Market - added by maple-market install.sh"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE=install
case "${1:-}" in --check) MODE=check;; --remove) MODE=remove;; "") ;; *) echo "Unknown option $1"; exit 2;; esac
STAMP=$(date +%Y%m%d-%H%M%S)

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '  \033[33m!!\033[0m  %s\n' "$*"; }
die()  { printf '\n\033[31mSTOPPED:\033[0m %s\nNo other site on this server was changed. Copy this window and send it to Claude.\n' "$*"; exit 1; }
ping_maple() { python3 -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=3)' \
                 "http://127.0.0.1:$1/api/ping" >/dev/null 2>&1; }
listening() { ss -ltn 2>/dev/null | grep -qE "[:.]$1[[:space:]]"; }

[[ $EUID -eq 0 ]] || die "Run this as root (log in as root@your-server, then run it)."
[[ "$DOMAIN" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$ ]] \
  || die "\"$DOMAIN\" isn't a web address like maple.example.com."
[[ -z "$EMAIL" || "$EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] || die "\"$EMAIL\" isn't an email address."

# ---------- 1. look around ----------
say "1. Looking at this server"
command -v python3 >/dev/null || die "python3 is missing. Install it with: apt install -y python3"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || die "python3 is older than 3.8."
ok "python3 $(python3 -c 'import platform; print(platform.python_version())')"
command -v systemctl >/dev/null || die "This server doesn't use systemd; tell Claude."

WEB_BUSY=0
if listening 80 || listening 443; then WEB_BUSY=1; fi
FRONT=none
if systemctl is-active --quiet nginx 2>/dev/null; then FRONT=nginx
elif systemctl is-active --quiet caddy 2>/dev/null; then FRONT=caddy
elif systemctl is-active --quiet cloudflared 2>/dev/null || pgrep -x cloudflared >/dev/null 2>&1; then FRONT=tunnel
elif [[ $WEB_BUSY -eq 0 ]]; then FRONT=fresh
fi
case "$FRONT" in
  fresh) ok "nothing serves websites here yet: nginx and an HTTPS certificate will be set up just for Maple";;
  none)  warn "something unknown is using the web ports (80/443); it will be left alone";;
  *)     ok "web front door: $FRONT";;
esac
echo "     programs on the web ports right now:"
(ss -ltnp 2>/dev/null | grep -E ':(80|443) ' | sed 's/^/       /') || echo "       (none found)"

# Is the address already used by a site that isn't Maple's? Then stop: two sites can't share it.
OWN_RE='/maple-market(\.conf)?$'
if [[ -d /etc/nginx ]]; then
  CLASH=$(grep -rlsE "server_name[^;]*[[:space:]]${DOMAIN//./\\.}([[:space:];]|$)" /etc/nginx 2>/dev/null | grep -vE "$OWN_RE|\.before-maple-" || true)
  [[ -z "$CLASH" ]] || die "nginx already has a site for $DOMAIN in: $CLASH. Pick another address with MAPLE_DOMAIN."
fi
if [[ -f /etc/caddy/Caddyfile ]] && grep -qE "^${DOMAIN//./\\.}([[:space:],{]|$)" /etc/caddy/Caddyfile \
   && ! grep -qF "$MARK" /etc/caddy/Caddyfile; then
  die "Caddy already has a site for $DOMAIN that Maple didn't add. Pick another address with MAPLE_DOMAIN."
fi
ok "the address $DOMAIN is free for Maple (or already Maple's)"

PORT=8790
if [[ -f "$ENVF" ]]; then PORT=$(grep -oP '^MAPLE_PORT=\K\d+' "$ENVF" || echo 8790); fi
if listening "$PORT" && ! ping_maple "$PORT"; then         # someone else's program has that port
  for p in 8791 8792 8793 8794 8795 8796 8797 8798; do listening "$p" || { PORT=$p; break; }; done
  listening "$PORT" && die "Ports 8790 to 8798 are all in use."
fi
ok "Maple market listens on 127.0.0.1:$PORT (only this server can reach it directly)"

if [[ $MODE == check ]]; then say "Check only: nothing was changed."; exit 0; fi

# ---------- taking the site down ----------
if [[ $MODE == remove ]]; then
  say "Taking the Maple site down"
  systemctl disable --now maple-market >/dev/null 2>&1 || true
  rm -f "$UNIT"; systemctl daemon-reload
  ok "service 'maple-market' stopped and removed"
  for f in /etc/nginx/sites-enabled/maple-market /etc/nginx/sites-available/maple-market /etc/nginx/conf.d/maple-market.conf; do
    [[ -e "$f" || -L "$f" ]] && { cp -P "$f" "/root/$(basename "$f").before-maple-remove-$STAMP" 2>/dev/null || true; rm -f "$f"; }
  done
  if [[ $FRONT == nginx ]]; then nginx -t >/dev/null 2>&1 && systemctl reload nginx && ok "nginx: Maple's entry removed"; fi
  CF=/etc/caddy/Caddyfile
  if [[ -f "$CF" ]] && grep -qF "$MARK" "$CF"; then
    cp "$CF" "$CF.before-maple-remove-$STAMP"
    # drop Maple's block (marker line to its closing brace) and the blank line the install put before it
    awk -v m="$MARK" '$0 == m {skip = 1; blank = 0; next} skip {if ($0 == "}") skip = 0; next}
                      blank {print ""; blank = 0} $0 == "" {blank = 1; next} {print} END {if (blank) print ""}' \
        "$CF.before-maple-remove-$STAMP" > "$CF"
    if caddy validate --config "$CF" --adapter caddyfile >/dev/null 2>&1; then systemctl reload caddy; ok "Caddy: Maple's block removed"
    else cp "$CF.before-maple-remove-$STAMP" "$CF"; warn "Caddy didn't accept the change, so the Caddyfile was put back."; fi
  fi
  [[ $FRONT == tunnel ]] && warn "Also remove the public hostname $DOMAIN from your Cloudflare tunnel."
  say "Done. The data is kept in $APP/data."
  echo "  To delete it all as well:  rm -rf /home/maple $ENVF && userdel maple"
  exit 0
fi

# ---------- 2. the program ----------
say "2. Installing the Maple market program"
id maple >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/maple --shell /usr/sbin/nologin maple
ok "user 'maple' (its own, separate from every other project)"
mkdir -p "$APP/data"
for f in server.py manage.py market.html icon.ico; do install -m 644 "$SRC/$f" "$APP/$f"; done
chown -R maple:maple /home/maple
chmod 750 "$APP/data"
ok "code in $APP (the data in $APP/data is kept on updates)"
if [[ ! -f "$ENVF" ]]; then
  printf 'MAPLE_PORT=%s\nMAPLE_DATA=%s/data\n' "$PORT" "$APP" > "$ENVF"
  ok "settings in $ENVF"
elif ! grep -qx "MAPLE_PORT=$PORT" "$ENVF"; then
  if grep -q '^MAPLE_PORT=' "$ENVF"; then sed -i "s/^MAPLE_PORT=.*/MAPLE_PORT=$PORT/" "$ENVF"; else echo "MAPLE_PORT=$PORT" >> "$ENVF"; fi
  ok "settings kept: $ENVF (port changed to $PORT: the old one is taken)"
else
  ok "settings kept: $ENVF"
fi
cat > "$UNIT" <<EOF
[Unit]
Description=Maple Classic Market ($DOMAIN)
After=network.target

[Service]
User=maple
EnvironmentFile=$ENVF
WorkingDirectory=$APP
ExecStart=/usr/bin/env python3 $APP/server.py
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$APP/data
PrivateTmp=true
MemoryMax=300M

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --quiet maple-market
systemctl restart maple-market
for _ in 1 2 3 4 5 6 7 8 9 10; do ping_maple "$PORT" && break; sleep 1; done
ping_maple "$PORT" || { journalctl -u maple-market -n 20 --no-pager; die "The Maple market didn't start (log above)."; }
ok "running (service 'maple-market'; no other service was touched)"

# ---------- 3. the web address ----------
say "3. Connecting $DOMAIN"
if [[ $FRONT == fresh ]]; then
  command -v apt-get >/dev/null || die "This isn't Ubuntu/Debian, so nginx can't be installed automatically; tell Claude."
  echo "     installing nginx and certbot (1 to 2 minutes)..."
  if ! { apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q nginx certbot python3-certbot-nginx; } >/tmp/maple-apt.log 2>&1; then
    tail -n 15 /tmp/maple-apt.log; die "Installing nginx didn't work (log above)."
  fi
  rm -f /etc/nginx/sites-enabled/default           # nginx's welcome page: on this droplet nginx is Maple's
  systemctl enable --quiet nginx; systemctl start nginx
  if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q 'Status: active'; then
    ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ok "firewall: web ports opened"
  fi
  ok "nginx installed"
  FRONT=nginx
fi
case "$FRONT" in
nginx)
  if [[ -d /etc/nginx/sites-enabled ]]; then SITE=/etc/nginx/sites-available/maple-market; LINK=/etc/nginx/sites-enabled/maple-market
  else SITE=/etc/nginx/conf.d/maple-market.conf; LINK=; fi
  mkdir -p "$(dirname "$SITE")"
  if [[ -f "$SITE" ]]; then
    if grep -q "proxy_pass http://127.0.0.1:$PORT;" "$SITE"; then
      ok "nginx already has the $DOMAIN entry"
    else                                            # the market moved to another port: point Maple's entry at it
      cp "$SITE" "/root/maple-market.nginx.before-$STAMP"
      sed -i "s#proxy_pass http://127.0.0.1:[0-9]*;#proxy_pass http://127.0.0.1:$PORT;#" "$SITE"
      if nginx -t >/dev/null 2>&1; then systemctl reload nginx; ok "nginx: Maple's entry now points at port $PORT"
      else cp "/root/maple-market.nginx.before-$STAMP" "$SITE"; die "nginx didn't accept the port change, so it was put back."; fi
    fi
  else
    V6="    listen [::]:80;"; [[ -e /proc/net/if_inet6 ]] || V6="    # (no IPv6 on this server)"
    cat > "$SITE" <<EOF
$MARK
# Remove this file (and its link in sites-enabled) to take the Maple site down; other sites have their own files.
server {
    listen 80;
$V6
    server_name $DOMAIN;
    client_max_body_size 3m;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF
    [[ -n "$LINK" ]] && ln -sf "$SITE" "$LINK"
    if nginx -t >/dev/null 2>&1; then
      systemctl reload nginx
      ok "nginx: new entry for $DOMAIN added and checked (other sites' entries untouched)"
    else
      rm -f "$SITE"; [[ -n "$LINK" ]] && rm -f "$LINK"
      nginx -t || true
      die "nginx didn't accept the new entry, so it was removed again. nginx is exactly as before."
    fi
  fi
  if command -v certbot >/dev/null; then
    who=(--register-unsafely-without-email); [[ -n "$EMAIL" ]] && who=(-m "$EMAIL")
    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos "${who[@]}" --redirect --keep-until-expiring >/tmp/maple-certbot.log 2>&1; then
      ok "HTTPS certificate for $DOMAIN (it renews by itself)"
    else
      warn "Couldn't get the HTTPS certificate yet (log: /tmp/maple-certbot.log)."
      warn "Usually the DNS record for $DOMAIN isn't in place yet. Add it (guide step 2), wait 5 minutes, then run this again."
    fi
  else
    warn "certbot isn't installed, so $DOMAIN works on http:// only. Tell Claude how this server's other sites get HTTPS."
  fi
  ;;
caddy)
  CF=/etc/caddy/Caddyfile
  if grep -qF "$MARK" "$CF" 2>/dev/null; then
    grep -q "reverse_proxy 127.0.0.1:$PORT\$" "$CF" && ok "Caddy already has $DOMAIN" \
      || warn "Caddy's Maple block points at another port; change it to 127.0.0.1:$PORT in $CF."
  else
    cp "$CF" "$CF.before-maple-$STAMP"
    printf '\n%s\n%s {\n\treverse_proxy 127.0.0.1:%s\n}\n' "$MARK" "$DOMAIN" "$PORT" >> "$CF"
    if caddy validate --config "$CF" --adapter caddyfile >/dev/null 2>&1; then
      systemctl reload caddy
      ok "Caddy: $DOMAIN added (HTTPS is automatic). Backup: $CF.before-maple-$STAMP"
    else
      cp "$CF.before-maple-$STAMP" "$CF"
      die "Caddy didn't accept the change, so the Caddyfile was put back exactly as it was."
    fi
  fi
  ;;
tunnel)
  warn "This server is reached through a Cloudflare tunnel. Add the address in Cloudflare (guide, 'tunnel'):"
  warn "  Public hostname: $DOMAIN   ->   Service: http://127.0.0.1:$PORT"
  ;;
*)
  warn "Another program (not nginx or Caddy) answers on the web ports, so Maple left it alone."
  warn "The Maple market is running, but $DOMAIN isn't connected yet. Send this window to Claude."
  ;;
esac

say "Done."
echo "  Make a key for yourself:   sudo -u maple python3 $APP/manage.py add YourName"
echo "  See the log:               journalctl -u maple-market -n 50 --no-pager"
echo "  Then open:                 https://$DOMAIN"
