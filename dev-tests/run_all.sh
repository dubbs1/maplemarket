#!/usr/bin/env bash
# Every check in one go (Linux/macOS). Usage:  bash dev-tests/run_all.sh [--quick] [--install]
#   --quick    skip the slow picture checks and the browser tests
#   --install  also run the install-script checks (ONLY in a throwaway container, as root)
# Needs: python3 with pillow, pytesseract, mss; tesseract; node + npm install; playwright for the browser tests.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT" || exit 1
export MAPLEREADER_UPDATE_API="${MAPLEREADER_UPDATE_API:-off}"   # checks never ask the real GitHub for updates
QUICK=0; INSTALL=0
for a in "$@"; do case "$a" in --quick) QUICK=1;; --install) INSTALL=1;; *) echo "unknown option $a"; exit 2;; esac; done
results=(); bad=0
run() {   # run <name> <command...>: one line per check, the output only when it fails
  local name="$1"; shift
  local out; out="$("$@" 2>&1)"; local code=$?
  if [[ $code == 0 ]]; then results+=("PASS  $name"); else results+=("FAIL  $name"); bad=1; printf '\n--- %s ---\n%s\n' "$name" "$out" | tail -n 40; fi
}
run "page copies match"  python3 tools/sync_market.py --check
run "market page"        npm test --silent
run "group server"       python3 maple-server/tests/test_server.py
run "group server (cloud)" python3 maple-cloud/tests/test_cloud.py
run "reader: session"    bash -c 'cd MapleReader && python3 tests/test_session.py'
run "reader: scrolling"  bash -c 'cd MapleReader && python3 tests/test_scroll.py'
run "reader: resizing"   bash -c 'cd MapleReader && python3 tests/test_resize.py'
run "reader: EXP tracker" bash -c 'cd MapleReader && python3 tests/test_exp.py'
run "reader: revisits"   bash -c 'cd MapleReader && python3 tests/test_revisit.py'
run "reader: app server" bash -c 'cd MapleReader && python3 tests/test_market.py'
run "reader: updates"    bash -c 'cd MapleReader && python3 tests/test_update.py'
if [[ $QUICK == 0 ]]; then
  run "reader: pictures" bash -c 'cd MapleReader && python3 tests/test_pictures.py'
  if python3 -c 'import playwright' 2>/dev/null; then
    for t in live_e2e app_e2e share_e2e; do run "browser: $t" python3 "dev-tests/e2e/$t.py"; done
  else
    results+=("SKIP  browser tests (pip install playwright)")
  fi
fi
[[ $INSTALL == 1 ]] && run "install script" bash -c 'bash dev-tests/e2e/test_install.sh | tee /dev/stderr | grep -q "ALL INSTALL CHECKS PASSED"'
printf '\n'; printf '%s\n' "${results[@]}"
[[ $bad == 0 ]] && echo "EVERYTHING PASSED" || echo "SOMETHING FAILED (details above)"
exit $bad
