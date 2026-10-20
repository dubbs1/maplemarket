"""One pretend friend: their own MapleReader (app backend + local page) scanning pretend frames."""
import sys, os, types, time, json
R, work, port, key, server, which, secs = sys.argv[1:8]
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, 'tests'))
os.makedirs(work, exist_ok=True); os.chdir(work)
import shopreader.config as C; C.APP_DIR = work
json.dump({'share_on': True, 'share_server': server, 'share_key': key, 'quiet': True}, open(os.path.join(work, 'settings.json'), 'w'))
from PIL import Image
if which == 'session':
    import test_session as TS; pics = TS.frames()
else:
    import test_scroll as SC
    fr = SC.build(['S100'] * 9 + ['S46'] + ['I0', 'I1', 'I2', 'I3', 'I4', 'I5'] + ['S100'] * 4)
    closed = Image.open(os.path.join(R, 'tests/fixtures/live_ch.png')).convert('RGB').resize(fr(0).size)
    pics = [closed] * 2 + [fr(0)] * 3 + sum(([fr(o)] * (3 if o in (3, 7, 10, 14) else 1) for o in range(1, 15)), []) + [closed] * 3
class Shot:
    def __init__(s, img): s.size, s.bgra = img.size, img.convert('RGBA').tobytes('raw', 'BGRA')
class Screen:
    monitors = [{}, {}]
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def grab(s, mon):
        time.sleep(0.1)
        return Shot(pics.pop(0) if len(pics) > 1 else pics[0])
sys.modules['mss'] = types.SimpleNamespace(MSS=lambda: Screen())
import shopreader.controller as CT, shopreader.market_server as M
CT.APP_DIR = M.APP_DIR = work; CT.SETTINGS = os.path.join(work, 'settings.json')
ctl = CT.Controller(); srv = M.MarketServer(controller=ctl, ports=[int(port)]); srv.start()
ch = 10 if which == 'session' else 3
ctl.start(channel=0 if which == 'session' else ch)
t0 = time.time()
while time.time() - t0 < float(secs):
    time.sleep(1)
    st = ctl.share_status()
    open(os.path.join(work, 'status.json'), 'w').write(json.dumps(dict(total=ctl.state['total'], share=st)))
ctl.shutdown(); srv.stop()
