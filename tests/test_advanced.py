import json, os, sys, tempfile, threading, time, unittest, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from border_watch.db import DB
from border_watch.engine import Engine
from border_watch.server import make_handler
from border_watch.video.detector import Detection, Detector
from border_watch.video.pipeline import Analyzer, ZoneSet
from border_watch.video.tracker import Tracker

class Stub:
    backend, note = "stub", ""
    def __init__(self, script): self.script, self.i = script, 0
    def feed(self, f): pass
    def reset(self): pass
    def detect(self, f):
        d = self.script[min(self.i, len(self.script) - 1)]; self.i += 1; return d

class Adv(unittest.TestCase):
    def test_passwords_hashed_and_verified(self):
        db = DB(os.path.join(tempfile.mkdtemp(), "t.db"))
        self.assertIsNone(db.verify("admin", "wrong")); self.assertEqual(db.verify("admin", "admin")["role"], "admin")
        row = db.all("SELECT hash,salt FROM users")[0]; self.assertNotIn("admin", row["hash"]); self.assertEqual(len(row["salt"]), 32)
        db.add_user("bob", "secret1", "viewer"); db.set_password("bob", "newpass1"); self.assertIsNone(db.verify("bob", "secret1")); self.assertTrue(db.verify("bob", "newpass1"))
        with self.assertRaises(ValueError): db.delete_user("admin")
        with self.assertRaises(ValueError): db.add_user("x y", "secret1", "viewer")
    def test_events_survive_restart(self):
        d = tempfile.mkdtemp(); e1 = Engine(data_dir=d); e1.cfg["demo"] = False; e1.world.auto = False
        rec = e1.store.add(cam="CAM-01", sector="North Sector", type="Drone Detection", objects="Drone", level=2, conf=.9, risk=.8)
        e1.act(rec["id"], "ack", "alice"); del e1
        e2 = Engine(data_dir=d); got = e2.store.get(rec["id"])
        self.assertEqual(got["status"], "ack"); self.assertEqual(got["by"], "alice")
    def test_policy_and_actor_recorded(self):
        e = Engine(data_dir=tempfile.mkdtemp()); e.cfg["demo"] = False; e.world.auto = False
        r = e.store.add(cam="CAM-01", sector="x", type="Drone Detection", objects="Drone", level=2, conf=.9, risk=.8)
        self.assertFalse(e.act(r["id"], "go", "op")["ok"]); self.assertTrue(e.act(r["id"], "ack", "op")["ok"]); self.assertTrue(e.act(r["id"], "go", "op")["ok"])
        self.assertEqual(e.store.get(r["id"])["by"], "op"); self.assertIsNotNone(e.store.get(r["id"])["resp"])
        self.assertFalse(e.command({"cmd": "set", "demo": True}, "v", "viewer")["ok"])
    def test_http_auth_and_roles(self):
        e = Engine(data_dir=tempfile.mkdtemp()); e.cfg["demo"] = False; e.world.auto = False
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(e, True)); srv.daemon_threads = True; port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start(); b = f"http://127.0.0.1:{port}"
        def call(path, body=None, cookie=None):
            rq = urllib.request.Request(b + path, None if body is None else json.dumps(body).encode(), {"Cookie": cookie} if cookie else {}, method="GET" if body is None else "POST")
            try:
                r = urllib.request.urlopen(rq); return r.status, json.loads(r.read()), r.headers.get("Set-Cookie")
            except urllib.error.HTTPError as ex: return ex.code, json.loads(ex.read()), None
        self.assertEqual(call("/api/state")[0], 401)
        self.assertEqual(call("/api/login", {"username": "admin", "password": "bad"})[0], 401)
        st, js, ck = call("/api/login", {"username": "admin", "password": "admin"}); self.assertEqual(st, 200); self.assertIn("HttpOnly", ck); ck = ck.split(";")[0]
        self.assertEqual(call("/api/state", cookie=ck)[0], 200)
        self.assertEqual(call("/api/users", {"op": "add", "username": "view1", "password": "viewpass", "role": "viewer"}, ck)[0], 200)
        _, _, vc = call("/api/login", {"username": "view1", "password": "viewpass"}); vc = vc.split(";")[0]
        self.assertEqual(call("/api/cmd", {"cmd": "act", "id": 1, "action": "ack"}, vc)[0], 403)
        self.assertEqual(call("/api/users", cookie=vc)[0], 403); self.assertEqual(call("/api/state", cookie=vc)[0], 200)
        for _ in range(5): call("/api/login", {"username": "admin", "password": "bad"})
        self.assertEqual(call("/api/login", {"username": "admin", "password": "admin"})[0], 429)
        srv.shutdown()
    def test_zone_polygon_and_crossing(self):
        Z = ZoneSet(200, 100, [dict(name="z", pts=[[.5, .5], [1, .5], [1, 1], [.5, 1]])])
        self.assertTrue(Z.inside(150, 80)); self.assertFalse(Z.inside(20, 20)); self.assertTrue(Z.is_near(95, 60))
        script = [[Detection("person", .9, (20 + 6 * i, 10, 40 + 6 * i, 60))] for i in range(40)]   # walks right into the zone
        an = Analyzer((100, 200, 3), Stub(script), polys=[dict(name="z", pts=[[.5, 0], [1, 0], [1, 1], [.5, 1]])]); evs = []
        for i in range(40): evs += an.process(np.zeros((100, 200, 3), np.uint8), i * .2)[1]
        self.assertEqual([e["type"] for e in evs], ["Unauthorized Crossing"])
    def test_tracker_predicts_fast_motion(self):
        tr = Tracker(640); ids = set(); x = 0
        for i, step in enumerate([20, 30, 40, 60, 80, 90, 90, 90, 90, 90]):     # a vehicle that accelerates to 90 px per detection
            x += step; ids |= {t.id for t in tr.update([Detection("vehicle", .9, (x, 100, x + 60, 140))], i * .5)}
        self.assertEqual(len(ids), 1)
    def test_clip_saved_and_webhook_sent(self):
        got = []
        class R(BaseHTTPRequestHandler):
            def do_POST(s): got.append(json.loads(s.rfile.read(int(s.headers["Content-Length"])))); s.send_response(200); s.send_header("Content-Length", "0"); s.end_headers()
            def log_message(s, *a): pass
        hs = HTTPServer(("127.0.0.1", 0), R); threading.Thread(target=hs.serve_forever, daemon=True).start()
        e = Engine(data_dir=tempfile.mkdtemp()); e.cfg["demo"] = False; e.world.auto = False
        self.assertTrue(e.command({"cmd": "set", "webhook_url": f"http://127.0.0.1:{hs.server_address[1]}/h", "webhook_min": 2})["ok"])
        self.assertFalse(e.command({"cmd": "set", "webhook_url": "ftp://x"})["ok"])
        r = e.store.add(cam="CAM-02", sector="East Sector", type="Vehicle Intrusion", objects="Vehicle", level=3, conf=.9, risk=1.2); e._notify(r)
        e.save_clip(r["id"], [b"\xff\xd8x" * 5] * 4)
        for _ in range(30):
            if got: break
            time.sleep(.1)
        hs.shutdown(); self.assertEqual(got[0]["event"]["type"], "Vehicle Intrusion"); self.assertEqual(got[0]["event"]["level"], "Critical")
        self.assertEqual(e.store.get(r["id"])["clip"], 4); self.assertTrue(os.path.exists(os.path.join(e.data, "clips", str(r["id"]), "003.jpg")))
    def test_zones_command_validated_and_persisted(self):
        d = tempfile.mkdtemp(); e = Engine(data_dir=d)
        e.command({"cmd": "set_zones", "cam": "CAM-01", "zones": [dict(name="A", pts=[[0, 0], [1, 0], [1, 1]]), dict(name="bad", pts=[[0, 0], [1, 1]])]})
        self.assertEqual(len(e.zones["CAM-01"]), 1); e2 = Engine(data_dir=d); self.assertEqual(e2.zones["CAM-01"][0]["name"], "A")
    def test_onnx_detector_runs(self):
        d = Detector("onnx"); self.assertEqual(d.backend, "onnx"); self.assertEqual(d.detect(np.zeros((360, 640, 3), np.uint8)), [])
if __name__ == "__main__": unittest.main()
