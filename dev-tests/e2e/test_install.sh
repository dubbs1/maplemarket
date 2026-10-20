#!/usr/bin/env bash
# Runs install.sh against stand-in tools in several situations and checks Rev Market's files never change.
# Needs root in a throwaway Linux machine or container (it writes to /etc and /home). Never run it on the real server.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="$ROOT/dev-tests/e2e/stubs:$PATH"
fail=0; check(){ if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }
reset(){ [[ -f /tmp/fake-maple.pid ]] && kill "$(cat /tmp/fake-maple.pid)" 2>/dev/null; rm -f /tmp/fake-maple.pid /tmp/fake-calls /tmp/fake-active-*
  rm -rf /home/maple /etc/maple-market.env /etc/systemd/system/maple-market.service /etc/nginx /etc/caddy; userdel maple 2>/dev/null
  mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled /etc/caddy /home/market/revenant-market /etc/systemd/system
  echo "server { server_name vendormarket.app; }" > /etc/nginx/sites-available/revenant-market; ln -sf /etc/nginx/sites-available/revenant-market /etc/nginx/sites-enabled/
  printf 'vendormarket.app {\n\treverse_proxy 127.0.0.1:3000\n}\n' > /etc/caddy/Caddyfile
  echo "SECRET=1" > /etc/revenant-market.env; echo "app" > /home/market/revenant-market/server.js; sleep 0.3; }
rev_sum(){ cat /etc/nginx/sites-available/revenant-market /etc/revenant-market.env /home/market/revenant-market/server.js | md5sum; }
I="$ROOT/maple-server/install.sh"

reset; before=$(rev_sum)
FAKE_ACTIVE="nginx" bash "$I" --check > /tmp/o.txt 2>&1
check "--check changes nothing" "[[ ! -d /home/maple && ! -f /etc/maple-market.env ]] && grep -q 'front door: nginx' /tmp/o.txt"

FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "nginx: install finishes" "[[ $code == 0 ]]"
check "nginx: service answers" "curl -fsS http://127.0.0.1:8790/api/ping | grep -q MapleMarket"
check "nginx: own site entry added and enabled" "grep -q 'server_name maple.vendormarket.app' /etc/nginx/sites-available/maple-market && [[ -L /etc/nginx/sites-enabled/maple-market ]]"
check "nginx: https certificate asked for" "grep -q 'certbot --nginx -d maple.vendormarket.app' /tmp/fake-calls"
check "nginx: Rev Market files unchanged" "[[ '$before' == \"\$(rev_sum)\" ]]"
check "runs as its own user" "pgrep -u maple -f maple-market/server.py >/dev/null"
sudo -u maple MAPLE_DATA=/home/maple/maple-market/data python3 /home/maple/maple-market/manage.py add Cass > /tmp/k.txt 2>&1 || runuser -u maple -- env MAPLE_DATA=/home/maple/maple-market/data python3 /home/maple/maple-market/manage.py add Cass > /tmp/k.txt
check "a key can be made" "grep -q 'Key for Cass' /tmp/k.txt"
echo "keep me" > /home/maple/maple-market/data/marker
FAKE_ACTIVE="nginx" bash "$I" > /tmp/o2.txt 2>&1; code=$?
check "update (run again): fine, data kept, nginx not touched twice" "[[ $code == 0 ]] && [[ -f /home/maple/maple-market/data/marker ]] && [[ -f /home/maple/maple-market/data/keys.json ]] && grep -q 'already has' /tmp/o2.txt"

reset; before=$(rev_sum)
FAKE_ACTIVE="nginx" FAKE_NGINX_OK=0 bash "$I" > /tmp/o.txt 2>&1; code=$?
check "nginx refuses the entry: stops, entry removed, Rev Market untouched" "[[ $code != 0 ]] && [[ ! -e /etc/nginx/sites-enabled/maple-market && ! -e /etc/nginx/sites-available/maple-market ]] && [[ '$before' == \"\$(rev_sum)\" ]]"

reset; FAKE_ACTIVE="nginx" FAKE_CERTBOT=1 bash "$I" > /tmp/o.txt 2>&1; code=$?
check "no certificate yet (DNS not ready): finishes with a clear note" "[[ $code == 0 ]] && grep -q 'DNS record' /tmp/o.txt"

reset; before=$(rev_sum); cf_before=$(md5sum < /etc/caddy/Caddyfile)
FAKE_ACTIVE="caddy" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "caddy: block added, backup kept, Rev Market block intact" "[[ $code == 0 ]] && grep -q '^maple.vendormarket.app' /etc/caddy/Caddyfile && grep -q '^vendormarket.app' /etc/caddy/Caddyfile && ls /etc/caddy/Caddyfile.before-maple-* >/dev/null"
reset; cf_before=$(md5sum < /etc/caddy/Caddyfile)
FAKE_ACTIVE="caddy" FAKE_CADDY_OK=1 bash "$I" > /tmp/o.txt 2>&1; code=$?
check "caddy refuses: Caddyfile put back exactly" "[[ $code != 0 ]] && [[ '$cf_before' == \"\$(md5sum < /etc/caddy/Caddyfile)\" ]]"

reset; FAKE_ACTIVE="cloudflared" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "cloudflare tunnel: running, tells you the hostname to add" "[[ $code == 0 ]] && grep -q 'http://127.0.0.1:8790' /tmp/o.txt"

reset; python3 -m http.server 8790 --bind 127.0.0.1 >/dev/null 2>&1 & busy=$!; sleep 1
FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "port 8790 already used by something else: picks another" "[[ $code == 0 ]] && grep -q 'MAPLE_PORT=8791' /etc/maple-market.env && grep -q '127.0.0.1:8791' /etc/nginx/sites-available/maple-market"
kill $busy

# --- a droplet of its own: nothing serves websites yet ---
fresh(){ reset; rm -rf /etc/nginx /etc/caddy; }
fresh; FAKE_ACTIVE="" bash "$I" --check > /tmp/o.txt 2>&1
check "fresh droplet --check: says nginx will be set up, installs nothing" "grep -q 'nothing serves websites' /tmp/o.txt && ! grep -q apt-get /tmp/fake-calls 2>/dev/null && [[ ! -d /home/maple ]]"
fresh; FAKE_ACTIVE="" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "fresh droplet: nginx and certbot installed, Maple's entry added" "[[ $code == 0 ]] && grep -q 'apt-get install.*nginx.*certbot' /tmp/fake-calls && grep -q 'server_name maple.vendormarket.app' /etc/nginx/sites-available/maple-market"
check "fresh droplet: nginx's welcome page switched off, certificate asked for" "[[ ! -e /etc/nginx/sites-enabled/default ]] && grep -q 'certbot --nginx -d maple.vendormarket.app' /tmp/fake-calls"
check "fresh droplet: service answers" "curl -fsS http://127.0.0.1:8790/api/ping | grep -q MapleMarket"
FAKE_ACTIVE="" bash "$I" > /tmp/o2.txt 2>&1; code=$?
check "fresh droplet, run again: uses the nginx it set up, installs nothing twice" "[[ $code == 0 ]] && grep -q 'front door: nginx' /tmp/o2.txt && [[ \$(grep -c 'apt-get install' /tmp/fake-calls) == 1 ]]"
fresh; FAKE_ACTIVE="" FAKE_UFW=active bash "$I" > /tmp/o.txt 2>&1
check "fresh droplet with the firewall on: web ports opened" "grep -q 'ufw allow 80/tcp' /tmp/fake-calls && grep -q 'ufw allow 443/tcp' /tmp/fake-calls"
fresh; FAKE_ACTIVE="" FAKE_APT_FAIL=1 bash "$I" > /tmp/o.txt 2>&1; code=$?
check "fresh droplet, nginx can't be installed: stops and says so" "[[ $code != 0 ]] && grep -q 'Installing nginx' /tmp/o.txt"

# --- the address ---
reset; before=$(rev_sum); echo "server { server_name shop.example maple.vendormarket.app; }" > /etc/nginx/sites-available/other-site
FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "address already used by another site: stops before changing anything" "[[ $code != 0 ]] && grep -q 'already has a site' /tmp/o.txt && [[ ! -d /home/maple && ! -f /etc/maple-market.env ]] && [[ '$before' == \"\$(rev_sum)\" ]]"
reset; MAPLE_DOMAIN=market.example.com MAPLE_EMAIL=me@example.com FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "own address and email" "[[ $code == 0 ]] && grep -q 'server_name market.example.com;' /etc/nginx/sites-available/maple-market && grep -q -- '-m me@example.com' /tmp/fake-calls"
reset; MAPLE_DOMAIN='x.com; rm -rf /' FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "an address that isn't one is refused" "[[ $code != 0 ]] && [[ ! -d /home/maple ]]"

# --- the port moves: settings and nginx entry follow ---
reset; FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1
kill "$(cat /tmp/fake-maple.pid)"; rm -f /tmp/fake-maple.pid; sleep 0.5
python3 -m http.server 8790 --bind 127.0.0.1 >/dev/null 2>&1 & busy=$!; sleep 1
FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "its port taken while it was stopped: moves to a free one, nginx follows" "[[ $code == 0 ]] && grep -qx 'MAPLE_PORT=8791' /etc/maple-market.env && grep -q 'proxy_pass http://127.0.0.1:8791;' /etc/nginx/sites-available/maple-market && curl -fsS http://127.0.0.1:8791/api/ping | grep -q MapleMarket"
kill $busy

# --- taking it down ---
reset; before=$(rev_sum); FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1
echo "keep me" > /home/maple/maple-market/data/marker
FAKE_ACTIVE="nginx" bash "$I" --remove > /tmp/o.txt 2>&1; code=$?
check "--remove (nginx): service and entry gone, data kept, Rev Market untouched" "[[ $code == 0 ]] && ! curl -fsS http://127.0.0.1:8790/api/ping >/dev/null 2>&1 && [[ ! -e /etc/nginx/sites-enabled/maple-market && ! -e /etc/nginx/sites-available/maple-market && ! -e /etc/systemd/system/maple-market.service ]] && [[ -f /home/maple/maple-market/data/marker ]] && [[ '$before' == \"\$(rev_sum)\" ]] && [[ -e /etc/nginx/sites-enabled/revenant-market ]]"
reset; cf_before=$(md5sum < /etc/caddy/Caddyfile); FAKE_ACTIVE="caddy" bash "$I" > /tmp/o.txt 2>&1
FAKE_ACTIVE="caddy" bash "$I" --remove > /tmp/o.txt 2>&1; code=$?
check "--remove (caddy): Caddyfile exactly as before Maple" "[[ $code == 0 ]] && [[ '$cf_before' == \"\$(md5sum < /etc/caddy/Caddyfile)\" ]]"
reset; before=$(rev_sum); FAKE_ACTIVE="" bash "$I" > /tmp/o.txt 2>&1; code=$?
check "nginx installed but stopped: refuses (it isn't a fresh droplet), Rev Market untouched" "[[ $code != 0 ]] && grep -q 'installed here but not running' /tmp/o.txt && [[ '$before' == \"\$(rev_sum)\" ]] && [[ ! -e /etc/nginx/sites-available/maple-market ]]"
reset; FAKE_ACTIVE="nginx" bash "$I" > /tmp/o.txt 2>&1; MAPLE_DOMAIN=new.example.com FAKE_ACTIVE="nginx" bash "$I" > /tmp/o2.txt 2>&1; code=$?
check "run again with another address: Maple's entry follows it" "[[ $code == 0 ]] && grep -q 'server_name new.example.com;' /etc/nginx/sites-available/maple-market && ! grep -q 'maple.vendormarket.app' /etc/nginx/sites-available/maple-market"
reset; rm -rf /etc/nginx /etc/caddy
echo; [[ $fail == 0 ]] && echo "ALL INSTALL CHECKS PASSED" || echo "SOME INSTALL CHECKS FAILED"
