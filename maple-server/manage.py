"""Look after the shared market's keys and data. Run on the server, for example:

  sudo -u maple python3 /home/maple/maple-market/manage.py add Gunther     # a key for a friend
  sudo -u maple python3 /home/maple/maple-market/manage.py list            # who has a key
  sudo -u maple python3 /home/maple/maple-market/manage.py revoke Gunther  # stop their key working
  sudo -u maple python3 /home/maple/maple-market/manage.py restore Gunther # let it work again
  sudo -u maple python3 /home/maple/maple-market/manage.py purge Gunther   # delete everything they sent
  sudo -u maple python3 /home/maple/maple-market/manage.py stats           # totals per person

Changes take effect straight away; no restart needed.
"""
import json
import os
import secrets
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server as S   # noqa: E402


def _read():
    try:
        with open(S.KEYS, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(keys):
    os.makedirs(S.DATA, exist_ok=True)
    tmp = S.KEYS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(keys, f, indent=1)
    os.replace(tmp, S.KEYS)


def _find(keys, name, active_only=False):
    return [h for h, v in keys.items() if v['name'].lower() == name.lower() and (v.get('active', True) or not active_only)]


def main(argv):
    if len(argv) < 2 or argv[1] not in ('add', 'list', 'revoke', 'restore', 'purge', 'stats'):
        print(__doc__)
        return 1
    cmd, name = argv[1], (' '.join(argv[2:]).strip() or None)
    keys = _read()
    if cmd in ('add', 'revoke', 'restore', 'purge') and not name:
        print('Give a name, for example:  manage.py', cmd, 'Gunther')
        return 1
    if cmd == 'add':
        if _find(keys, name, active_only=True):
            print(f'{name} already has a key that works. Revoke it first if you want to give them a new one.')
            return 1
        key = 'mm-' + secrets.token_urlsafe(18)
        keys[S.hash_key(key)] = {'name': name, 'active': True, 'created': time.strftime('%Y-%m-%d')}
        _write(keys)
        print(f'Key for {name}:  {key}')
        print('Send it to them privately. It is shown only once (only a scrambled copy is stored).')
        return 0
    if cmd == 'list':
        if not keys:
            print('No keys yet. Make one with:  manage.py add <name>')
        for v in sorted(keys.values(), key=lambda v: v['name'].lower()):
            print(f"{v['name']:<20} {'active' if v.get('active', True) else 'REVOKED':<8} since {v.get('created', '?')}")
        return 0
    if cmd in ('revoke', 'restore'):
        hs = _find(keys, name)
        if not hs:
            print(f'No key named {name}.')
            return 1
        if cmd == 'restore':
            if any(keys[h].get('active', True) for h in hs):
                print(f"{name}'s newest key already works; older keys stay revoked.")
                return 1
            hs = hs[-1:]                              # only the newest key comes back
        for h in hs:
            keys[h]['active'] = cmd == 'restore'
        _write(keys)
        print(f"{name}'s key {'works again' if cmd == 'restore' else 'no longer works'}.")
        return 0
    con = S.db()
    if cmd == 'purge':
        n = con.execute('DELETE FROM rows WHERE lower(who) = lower(?)', (name,)).rowcount
        con.commit()
        print(f'Deleted {n} listings sent by {name}. Pages pick this up after "Reload all".')
        return 0
    if cmd == 'stats':
        for who, n, last in con.execute('SELECT who, COUNT(*), MAX(at) FROM rows GROUP BY who ORDER BY 2 DESC'):
            print(f'{who:<20} {n:>7} listings   last sent {time.strftime("%Y-%m-%d %H:%M", time.localtime(last))}')
        print('total', con.execute('SELECT COUNT(*) FROM rows').fetchone()[0])
        return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
