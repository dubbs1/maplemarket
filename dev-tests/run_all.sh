#!/usr/bin/env bash
# Every check in one go (Linux/macOS). Usage:  bash dev-tests/run_all.sh [--quick]
#   --quick    skip the browser test
# Needs: python3 with pillow, pytesseract, mss; tesseract; playwright for the browser test.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT" || exit 1
export MAPLEREADER_UPDATE_API="${MAPLEREADER_UPDATE_API:-off}"   # checks never ask the real GitHub for updates
QUICK=0
for a in "$@"; do case "$a" in --quick) QUICK=1;; *) echo "unknown option $a"; exit 2;; esac; done
results=(); bad=0
run() {   # run <name> <command...>: one line per check, the output only when it fails
  local name="$1"; shift
  local out; out="$("$@" 2>&1)"; local code=$?
  if [[ $code == 0 ]]; then results+=("PASS  $name"); else results+=("FAIL  $name"); bad=1; printf '\n--- %s ---\n%s\n' "$name" "$out" | tail -n 40; printf '%s\n' "$out" | grep -E '^ *FAIL|Error|Traceback' | head -n 10; fi
}
run "reader: EXP tracker" bash -c 'cd MapleReader && python3 tests/test_exp.py'
run "reader: mob pictures" bash -c 'cd MapleReader && python3 tests/test_mobpics.py'
run "reader: app server" bash -c 'cd MapleReader && python3 tests/test_server.py'
run "reader: updates"    bash -c 'cd MapleReader && python3 tests/test_update.py'
if [[ $QUICK == 0 ]]; then
  if python3 -c 'import playwright' 2>/dev/null; then
    run "browser: app_e2e" python3 dev-tests/e2e/app_e2e.py
  else
    results+=("SKIP  browser test (pip install playwright)")
  fi
fi
printf '\n'; printf '%s\n' "${results[@]}"
[[ $bad == 0 ]] && echo "EVERYTHING PASSED" || echo "SOMETHING FAILED (details above)"
exit $bad
