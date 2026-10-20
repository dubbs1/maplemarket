#!/usr/bin/env bash
# Installs or updates the Maple market on this server, next to (never inside) Rev Market.
#   bash install.sh            install / update
#   bash install.sh --check    only look around and report; changes nothing
#
# What it touches:   /home/maple/maple-market (code + data), /etc/maple-market.env,
#                    /etc/systemd/system/maple-market.service, and ONE new site entry for
#                    maple.vendormarket.app in the web front door (nginx or Caddy), backed up first.
# What it never touches: anything of Rev Market (/home/market, (its own folder), (its own settings file)).
set -euo pipefail

DOMAIN="${MAPLE_DOMAIN:-maple.vendormarket.app}"
APP=/home/maple/maple-market
ENVF=/etc/maple-market.env
UNIT=/etc/systemd/system/maple-market.service
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK=0; [[ "${1:-}" == "--check" ]] && CHECK=1
STAMP=$(date +%Y%m%d-%H%M%S)

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '  \033[33m!!\033[0m  %s\n' "$*"; }
die()  { printf '\n\033[31mSTOPPED:\033[0m %s\nNothing of Rev Market was changed. Copy this window and send it to Claude.\n' "$*"; exit 1; }

[[ $EUID -eq 0 ]] || die "Run this as root (you log in as root@your-server, so just run it from there)."

# ---------- 1. look around ----------
say "1. Looking at this server"
command -v python3 >/dev/null || die "python3 is missing. Install it with: apt install -y python3"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || die "python3 is older than 3.8."
ok "python3 $(python3 -c 'import platform; print(platform.python_version())')"
command -v systemctl >/dev/null || die "This server doesn't use systemd; tell Claude."

FRONT=none
if systemctl is-active --quiet nginx 2>/dev/null; then FRONT=nginx
elif systemctl is-active --quiet caddy 2>/dev/null; then FRONT=caddy
elif systemctl is-active --quiet cloudflared 2>/dev/null || pgrep -x cloudflared >/dev/null 2>&1; then FRONT=tunnel
fi
ok "web front door: $FRONT"
echo "     programs on the web ports right now:"
(ss -ltnp 2>/dev/null | grep -E ':(80|443) ' | sed 's/^/       /') || echo "       (none found)"

PORT=8790
if [[ -f "$ENVF" ]]; then PORT=$(grep -oP '^MAPLE_PORT=\K\d+' "$ENVF" || echo 8790); fi
if ss -ltn 2>/dev/null | grep -q ":$PORT " && ! systemctl is-active --quiet maple-market; then
  for p in 8791 8792 8793 8794 8795; do ss -ltn | grep -q ":$p " || { PORT=$p; break; }; done
fi
ok "Maple market will listen on 127.0.0.1:$PORT (only this server can reach it directly)"

if [[ $CHECK -eq 1 ]]; then say "Check only: nothing was changed."; exit 0; fi

# ---------- 2. the program ----------
say "2. Installing the Maple market program"
id maple >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/maple --shell /usr/sbin/nologin maple
ok "user 'maple' (separate from Rev Market's user)"
mkdir -p "$APP/data"
for f in server.py manage.py market.html icon.ico; do install -m 644 "$SRC/$f" "$APP/$f"; done
chown -R maple:maple /home/maple
chmod 750 "$APP/data"
ok "code in $APP (your data in $APP/data is kept on updates)"
if [[ ! -f "$ENVF" ]]; then
  printf 'MAPLE_PORT=%s\nMAPLE_DATA=%s/data\n' "$PORT" "$APP" > "$ENVF"
  ok "settings in $ENVF"
else
  ok "settings kept: $ENVF"
fi
cat > "$UNIT" <<EOF
[Unit]
Description=Maple Classic Market (maple.vendormarket.app)
After=network.target

[Service]
User=maple
EnvironmentFile=$ENVF
WorkingDirectory=$APP
ExecStart=/usr/bin/env python3 $APP/server.py
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=$APP/data

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --quiet maple-market
systemctl restart maple-market
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -fsS "http://127.0.0.1:$PORT/api/ping" >/dev/null 2>&1 && break; sleep 1
done
curl -fsS "http://127.0.0.1:$PORT/api/ping" >/dev/null 2>&1 || { journalctl -u maple-market -n 20 --no-pager; die "The Maple market didn't start (log above)."; }
ok "running (service 'maple-market'; Rev Market's service was not touched)"

# ---------- 3. the web address ----------
say "3. Connecting $DOMAIN"
case "$FRONT" in
nginx)
  SITE=/etc/nginx/sites-available/maple-market
  if [[ -f "$SITE" ]]; then
    ok "nginx already has the $DOMAIN entry"
  else
    cat > "$SITE" <<EOF
# Maple Classic Market - added by maple-market install.sh. Remove this file and its link in
# sites-enabled to take the Maple site down; Rev Market's own entry is a different file.
server {
    listen 80;
    listen [::]:80;
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
    ln -sf "$SITE" /etc/nginx/sites-enabled/maple-market
    if nginx -t >/dev/null 2>&1; then
      systemctl reload nginx
      ok "nginx: new entry for $DOMAIN added and checked (Rev Market's entry untouched)"
    else
      rm -f /etc/nginx/sites-enabled/maple-market "$SITE"
      nginx -t || true
      die "nginx didn't accept the new entry, so it was removed again. nginx is exactly as before."
    fi
  fi
  if command -v certbot >/dev/null; then
    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect --keep-until-expiring >/tmp/maple-certbot.log 2>&1; then
      ok "HTTPS certificate for $DOMAIN"
    else
      warn "Couldn't get the HTTPS certificate yet (log: /tmp/maple-certbot.log)."
      warn "Usually the DNS record for $DOMAIN isn't in place yet. Add it (guide step A), wait 5 minutes, then run this again."
    fi
  else
    warn "certbot isn't installed, so $DOMAIN works on http:// only. Tell Claude which way Rev Market gets its HTTPS."
  fi
  ;;
caddy)
  CF=/etc/caddy/Caddyfile
  if grep -q "^$DOMAIN" "$CF" 2>/dev/null; then
    ok "Caddy already has $DOMAIN"
  else
    cp "$CF" "$CF.before-maple-$STAMP"
    printf '\n# Maple Classic Market - added by maple-market install.sh\n%s {\n\treverse_proxy 127.0.0.1:%s\n}\n' "$DOMAIN" "$PORT" >> "$CF"
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
  warn "This server is reached through a Cloudflare tunnel. Add the address in Cloudflare (guide step A, 'tunnel'):"
  warn "  Public hostname: $DOMAIN   ->   Service: http://127.0.0.1:$PORT"
  ;;
*)
  warn "No nginx, Caddy or Cloudflare tunnel found in front of Rev Market."
  warn "The Maple market is running, but $DOMAIN isn't connected yet. Send this window to Claude."
  ;;
esac

say "Done."
echo "  Make a key for yourself:   sudo -u maple python3 $APP/manage.py add YourName"
echo "  See the log:               journalctl -u maple-market -n 50 --no-pager"
echo "  Then open:                 https://$DOMAIN"
