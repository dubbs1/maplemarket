"""Your mobs list (mobs.txt next to the app): which mob gives how much EXP, so the kills the EXP tracker counts
can be named. One mob per line, parts split by | or tabs:  name | level | HP | EXP  (level and HP may be left out:
name and EXP are enough). Lines starting with # are notes. The numbers may have commas (1,200).

A kill is seen as a jump in your EXP, so a mob is known by its EXP: two mobs with the same EXP can't be told
apart (both names are shown). The list isn't shipped with the app: copy it from the MapleClassic Wiki
(CC BY-NC-SA, credit them) or type the mobs you hunt."""
import os
import re
import time

TEMPLATE = """# Your mobs list, for the EXP tab's kill counts. One mob per line:  name | level | HP | EXP
# (level and HP may be left out; the numbers may have commas). Lines starting with # are notes.
# A mob is told by the EXP one kill gives, so only the EXP has to be right. Copy from the MapleClassic Wiki
# (mapleclassic.wiki, CC BY-NC-SA: credit them) or type the mobs you hunt, then save this file: MapleReader
# re-reads it by itself.
#
# Snail | 1 | 8 | 3
"""


def parse_mobs(text):
    """{exp: [names]} from the file's text."""
    out = {}
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        p = [x.strip() for x in re.split(r'[|\t]', ln) if x.strip()]
        if len(p) < 2 or len(p[0]) > 60:
            continue
        exp = p[-1].replace(',', '')
        if not exp.isdigit() or not 0 < int(exp) < 100_000_000:
            continue
        names = out.setdefault(int(exp), [])
        if p[0] not in names:
            names.append(p[0])
    return out


class Mobs:
    """mobs.txt, re-read when it changes (checked at most every few seconds)."""
    CHECK = 5

    def __init__(self, path):
        self.path, self.table, self.stamp, self.checked = path, {}, None, 0

    def ensure(self):
        """Write the template if there's no file yet (so the owner finds where to type)."""
        try:
            if not os.path.exists(self.path):
                with open(self.path, 'w', encoding='utf-8') as f:
                    f.write(TEMPLATE)
        except OSError:
            pass

    def load(self, now=None):
        now = time.time() if now is None else now
        if now - self.checked < self.CHECK:
            return self.table
        self.checked = now
        try:
            stamp = os.stat(self.path).st_mtime_ns
        except OSError:
            self.table, self.stamp = {}, None
            return self.table
        if stamp != self.stamp:
            try:
                with open(self.path, encoding='utf-8-sig') as f:     # -sig: Notepad's invisible first character
                    self.table = parse_mobs(f.read())
                self.stamp = stamp
            except OSError:
                pass
        return self.table

    def name(self, exp):
        """The mob (or mobs: "A / B") that gives this much EXP, or None if it isn't in the list."""
        names = self.load().get(exp)
        return ' / '.join(names) if names else None
