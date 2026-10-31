"""Engine: simulated demo sensors, camera workers (uploaded video / webcam / stream), shared event store, settings and audit."""
import collections, json, os, re, shutil, threading, time, urllib.request
import datetime as dt
from . import config as C
from .db import DB, ROLES
from .simulator import World
from .agents import Orchestrator
from .store import EventStore, CAMS, STATUS_NAMES, answer
from . import video as V

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
SIM_TYPES = ["Unauthorized Crossing", "Group Movement", "Loitering", "Vehicle Intrusion", "Drone Detection", "Abandoned Object", "Fence Breach"]
SIM_OBJ = ["Person", "{n} Persons", "Person", "Vehicle", "Drone", "Object", "Fence"]
PERM = {"act": 1, "cam_pause": 1, "cam_source": 1, "set_zones": 1, "inject": 2, "set": 2, "clear_events": 2, "reset": 2, "test_webhook": 2}
CLIP_FPS, PRE, POST = 6, 4, 3                 # event replay: frames per second, seconds before, seconds after

class CameraWorker(threading.Thread):
    def __init__(self, engine, cam, sector):
        super().__init__(daemon=True)
        self.eng, self.cam, self.sector = engine, cam, sector
        self.src, self.name, self.gen, self.paused, self.status = None, "", 0, False, "idle"
        self.jpeg, self.fps, self.analyzer, self.is_file, self.proc_ms = None, 0.0, None, True, 0.0
        self.last_raw, self.ring, self.pending, self.zones_seen = None, collections.deque(maxlen=PRE * CLIP_FPS), [], -1
        self.start()

    def set_source(self, src, name=""):
        self.src, self.name, self.paused, self.jpeg, self.analyzer = src, name, False, None, None
        self.status = "starting" if src is not None else "idle"; self.gen += 1

    def run(self):
        import cv2
        from .video.pipeline import Analyzer
        from .video.detector import Detector
        while True:
            if self.src is None: time.sleep(0.2); continue
            gen, src = self.gen, self.src
            cap = cv2.VideoCapture(int(src) if str(src).isdigit() else src)
            if not cap.isOpened():
                self.status = "error"; self.src = None; self.eng.say(f"{self.cam}: could not open the video source."); continue
            self.is_file = not (str(src).isdigit() or "://" in str(src))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0; fps = min(60.0, max(5.0, fps)); self.fps = fps
            stride = max(1, int(fps / 6)); cstride = max(1, int(fps / CLIP_FPS)); idx = 0; started = time.time(); an = None; passes = 0
            self.ring.clear(); self.pending.clear(); self.status = "live"
            while gen == self.gen:
                if self.paused: self.status = "paused"; time.sleep(0.1); continue
                self.status = "live"; t0 = time.time(); ok, frame = cap.read()
                if not ok:
                    if self.is_file and self.eng.cfg["loop"]:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0); idx = 0; passes += 1
                        if an: an.reset()
                        continue
                    self.status = "ended"; break
                h, w = frame.shape[:2]
                if w > 960: frame = cv2.resize(frame, (960, int(h * 960 / w))); h, w = frame.shape[:2]
                if an is None:
                    try: det = Detector(self.eng.backend, self.eng.model, imgsz=self.eng.imgsz)
                    except Exception as ex:
                        self.eng.say(f"{self.cam}: detector error: {ex}"); self.status = "error"; self.src = None; break
                    an = Analyzer(frame.shape, det, self.eng.fence.get(self.cam, .45), self.eng.zones.get(self.cam) or None)
                    self.analyzer = an; self.zones_seen = self.eng.zones_ver.get(self.cam, 0)
                if self.zones_seen != self.eng.zones_ver.get(self.cam, 0):
                    self.zones_seen = self.eng.zones_ver.get(self.cam, 0); an.set_zones(self.eng.zones.get(self.cam) or None, self.eng.fence.get(self.cam, .45))
                an.show_trails, an.show_heat, an.enhance = self.eng.cfg["trails"], self.eng.cfg["heat"], self.eng.cfg["enhance"]
                self.last_raw = frame
                t = idx / fps if self.is_file else time.time() - started
                try: out, events = an.process(frame, t, detect=(idx % stride == 0))
                except Exception as ex:
                    self.eng.say(f"{self.cam}: analysis error {type(ex).__name__}: {ex}"); out, events = frame, []
                self.jpeg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 72])[1].tobytes()
                if idx % cstride == 0:                                   # replay buffer
                    sm = cv2.resize(out, (480, int(h * 480 / w))) if w > 480 else out
                    jb = cv2.imencode(".jpg", sm, [cv2.IMWRITE_JPEG_QUALITY, 62])[1].tobytes(); self.ring.append(jb)
                    for p in list(self.pending):
                        p["frames"].append(jb); p["left"] -= 1
                        if p["left"] <= 0: self.pending.remove(p); self.eng.save_clip(p["id"], p["frames"])
                if passes == 0:                                          # looped replays are display only
                    for ev in events:
                        rec = self.eng.on_video_event(self.cam, self.sector, ev)
                        if rec: self.pending.append(dict(id=rec["id"], frames=list(self.ring), left=POST * CLIP_FPS))
                idx += 1; el = time.time() - t0; self.proc_ms = .9 * self.proc_ms + .1 * el * 1000
                time.sleep(max(0.0, 1.0 / fps - el))
            cap.release()
            if self.status not in ("ended", "error"): self.status = "idle" if self.src is None else self.status

class Engine:
    def __init__(self, seed=None, backend="auto", model="", imgsz=None, data_dir=DATA):
        self.lock = threading.RLock(); self.backend, self.model, self.imgsz, self.data = backend, model, imgsz, data_dir
        for sub in ("uploads", "evidence", "clips"): os.makedirs(os.path.join(data_dir, sub), exist_ok=True)
        self.db = DB(os.path.join(data_dir, "borderwatch.db"))
        self.cfg = dict(loop=True, trails=False, heat=False, enhance=True, webhook_url="", webhook_min=2, demo=True)
        self.cfg.update(self.db.get("cfg", {}))
        self.zones = {c: self.db.get("zones:" + c, []) for c, _ in CAMS}; self.fence = {c: self.db.get("fence:" + c, .45) for c, _ in CAMS}
        self.zones_ver = {c: 0 for c, _ in CAMS}
        self.log = collections.deque(maxlen=200); self.seed = seed; self.mirror = {}; self.video_alerts = 0
        self.store = EventStore(self.db)
        for e in self.store.events:                                       # simulated events cannot survive a restart
            if e["src"] == "sim" and e["status"] in ("new", "ack"): e["status"] = "expired"; self.store.save(e)
        self._new_world()
        self.say("Console started. All agents online.")
        self.cams = {c: CameraWorker(self, c, s) for c, s in CAMS} if V.AVAILABLE else {}
        threading.Thread(target=self._sim_loop, daemon=True).start()

    def _new_world(self):
        self.world = World(self.seed); self.world.auto = self.cfg["demo"]; self.orch = Orchestrator(self.world); self.orch.say = self.say; self.mirror = {}

    def say(self, msg, user=None):
        self.log.appendleft((time.time(), (f"[{user}] " if user else "") + msg)); self.db.log(msg, user)

    def save_cfg(self): self.db.put("cfg", self.cfg)

    # ---- simulated demo sensors -----------------------------------
    def _sim_loop(self):
        while True:
            with self.lock:
                if self.cfg["demo"]: self.orch.step(0.1); self._mirror()
            time.sleep(0.1)

    def _mirror(self):
        for a in list(self.orch.alert.alerts.values()):
            tr = self.orch.tracks.get(a.id)
            if a.id not in self.mirror and tr and tr.pos:
                x = tr.pos[-1][1]; ci = max(0, min(4, int(x / 180))); cam, sector = CAMS[ci]
                k = a.top if a.lvl != "U" else None
                typ = SIM_TYPES[k] if k is not None and k < 7 else ("Raw Sensor Alarm" if a.lvl == "U" else "Other")
                obj = SIM_OBJ[k].format(n=tr.gs) if k is not None and k < 7 else "Unknown"
                lvl = 1 if a.lvl == "U" else a.lvl
                e = self.store.add(cam=cam, sector=sector, type=typ, objects=obj, level=lvl, risk=round(a.risk, 2), conf=round(a.th, 2),
                                   src="sim", ref=a.id, channels=a.channels, status="logged" if lvl == 0 else "new")
                self.mirror[a.id] = e["id"]; self._notify(e)
            elif a.id in self.mirror:
                e = self.store.get(self.mirror[a.id]); before = (e["level"], e["status"], e["esc"], e["conf"])
                if a.lvl != "U": e["level"], e["conf"], e["risk"] = a.lvl, round(a.th, 2), round(a.risk, 2)
                if e["status"] in ("new", "ack", "logged"):
                    e["status"] = {"new": "new", "ack": "ack", "digest": "logged", "lost": "expired", "withdrawn": "withdrawn"}.get(a.status, e["status"])
                    if e["level"] == 0 and e["status"] == "new": e["status"] = "logged"
                e["esc"] = a.escalated
                if before != (e["level"], e["status"], e["esc"], e["conf"]): self.store.save(e)

    # ---- video events -----------------------------------------------
    def on_video_event(self, cam, sector, ev):
        import cv2
        with self.lock:
            now = time.time()
            if any(e["cam"] == cam and e["type"] == ev["type"] and e["src"] == "video" and now - e["ts"] < 8 for e in self.store.events[-30:]): return None
            lvl = ev["level"]
            rec = self.store.add(cam=cam, sector=sector, type=ev["type"], objects=ev["objects"], level=lvl, risk=ev["risk"], conf=ev["conf"],
                                 channels=C.CHANNELS[lvl], status="logged" if lvl == 0 else "new", snap=True)
            self.video_alerts += 1
            if lvl > 0: self.orch.n["op"] += 1
            self.say(f"#{rec['id']} {cam}: {ev['type']} ({ev['objects']}), {C.LEVELS[lvl]} risk, confidence {ev['conf']:.2f}. Channels: {', '.join(C.CHANNELS[lvl])}.")
        cv2.imwrite(os.path.join(self.data, "evidence", f"{rec['id']}.jpg"), ev["frame"])
        self._notify(rec)
        return rec

    def save_clip(self, eid, frames):
        d = os.path.join(self.data, "clips", str(eid)); os.makedirs(d, exist_ok=True)
        for i, b in enumerate(frames):
            with open(os.path.join(d, f"{i:03d}.jpg"), "wb") as f: f.write(b)
        with self.lock:
            e = self.store.get(eid)
            if e: e["clip"] = len(frames); self.store.save(e)

    def _notify(self, rec):
        url = self.cfg.get("webhook_url", "")
        if not url or rec["level"] < self.cfg.get("webhook_min", 2): return
        body = json.dumps(dict(source="Border Watch", event=dict(id=rec["id"], time=dt.datetime.fromtimestamp(rec["ts"]).isoformat(timespec="seconds"),
              camera=rec["cam"], sector=rec["sector"], type=rec["type"], objects=rec["objects"], level=C.LEVELS[rec["level"]],
              risk=rec.get("risk"), confidence=rec["conf"], origin=rec["src"]))).encode()
        def go():
            try:
                with urllib.request.urlopen(urllib.request.Request(url, body, {"Content-Type": "application/json"}), timeout=5) as r:
                    self.say(f"Webhook delivered for #{rec['id']} (HTTP {r.status}).")
            except Exception as ex: self.say(f"Webhook failed for #{rec['id']}: {type(ex).__name__}")
        threading.Thread(target=go, daemon=True).start()

    # ---- operator -----------------------------------------------------
    def act(self, eid, action, user=None):
        with self.lock:
            e = self.store.get(eid); o = self.orch
            if not e: return dict(ok=False, msg="Event not found.")
            if e["status"] not in ("new", "ack"): return dict(ok=False, msg="Event is already closed.")
            if action not in ("ack", "go", "no"): return dict(ok=False, msg="Unknown action.")
            if action == "go" and e["level"] >= 2 and e["status"] != "ack":
                o.n["blocked"] += 1; self.say(f"BLOCKED: #{eid} needs acknowledgement before dispatch.", user)
                return dict(ok=False, msg="Policy: acknowledge High and Critical alerts before dispatching.")
            if e["src"] == "sim":
                ok, msg = o.operator(e["ref"], action)
                if not ok: return dict(ok=False, msg=msg)
            elif action == "go": o.request_tool("orchestrator", "dispatch_response", approved=True)
            e["status"] = {"ack": "ack", "go": "done", "no": "dismissed"}[action]; e["by"] = user
            if action == "go": e["resp"] = round(time.time() - e["ts"], 1)
            if e["src"] != "sim": self.say({"ack": f"Operator acknowledged #{eid}.", "go": f"Response dispatched to #{eid} after {e['resp'] if action == 'go' else 0:.0f} s.",
                      "no": f"#{eid} dismissed as a false alarm. Label saved."}[action], user)
            self.store.save(e)
            return dict(ok=True, msg="Done.")

    # ---- commands -------------------------------------------------------
    def command(self, d, user=None, role="admin"):
        k = d.get("cmd")
        if ROLES.get(role, 0) < PERM.get(k, 2): return dict(ok=False, msg="Your role does not allow this action.")
        with self.lock:
            w, o = self.world, self.orch
            if k == "act": return self.act(int(d["id"]), d["action"], user)
            if k == "inject": w.spawn(int(d["cls"])); self.say(f"Injected demo event: {C.NAMES[int(d['cls'])]}.", user)
            elif k == "set":
                for key in ("demo", "loop", "trails", "heat", "enhance"):
                    if key in d: self.cfg[key] = bool(d[key])
                if "demo" in d: w.auto = self.cfg["demo"]
                if "webhook_url" in d:
                    u = str(d["webhook_url"]).strip()
                    if u and not re.match(r"^https?://", u): return dict(ok=False, msg="Webhook URL must start with http:// or https://")
                    self.cfg["webhook_url"] = u
                if "webhook_min" in d: self.cfg["webhook_min"] = max(0, min(3, int(d["webhook_min"])))
                for key, attr in (("night", "night"), ("bad", "bad_weather")):
                    if key in d: setattr(w, attr, bool(d[key]))
                if "agents_on" in d: o.agents_on = bool(d["agents_on"])
                if "tau" in d: o.tau = float(d["tau"])
                self.save_cfg(); self.say("Settings changed.", user)
            elif k == "cam_pause" and d["cam"] in self.cams: self.cams[d["cam"]].paused = bool(d["paused"])
            elif k == "cam_source" and d["cam"] in self.cams:
                src = str(d.get("src", "")).strip()
                self.cams[d["cam"]].set_source(src or None, src); self.say(f"{d['cam']}: source set to {src or 'none'}.", user)
            elif k == "set_zones" and d["cam"] in self.zones:
                zs = []
                for z in (d.get("zones") or [])[:8]:
                    pts = [[min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))] for x, y in z["pts"]][:40]
                    if len(pts) >= 3: zs.append(dict(name=str(z.get("name", "Zone"))[:40], pts=pts))
                self.zones[d["cam"]] = zs
                if "fence_y" in d: self.fence[d["cam"]] = min(.9, max(.1, float(d["fence_y"]))); self.db.put("fence:" + d["cam"], self.fence[d["cam"]])
                self.db.put("zones:" + d["cam"], zs); self.zones_ver[d["cam"]] += 1
                self.say(f"{d['cam']}: {len(zs) or 'default'} restricted zone(s) saved.", user)
            elif k == "clear_events":
                self.store.clear(); self.mirror.clear(); self.say("All events cleared.", user)
            elif k == "reset": self._new_world(); self.say("Demo sensors reset.", user)
            elif k == "test_webhook":
                u = self.cfg.get("webhook_url")
                if not u: return dict(ok=False, msg="Set a webhook URL first.")
                self._notify(dict(id=0, ts=time.time(), cam="TEST", sector="Test", type="Webhook Test", objects="n/a", level=3, risk=0, conf=1, src="test"))
        return dict(ok=True)

    def add_upload(self, cam, name, path, user=None):
        if cam not in self.cams: return dict(ok=False, msg="Unknown camera.")
        self.cams[cam].set_source(path, name)
        with self.lock:
            if self.cfg["demo"]:
                self.cfg["demo"] = False; self.world.auto = False; self.save_cfg(); self.say("Demo data switched off because a video was uploaded.")
            self.say(f"{cam}: video '{name}' loaded. Analysis started.", user)
        return dict(ok=True)

    # ---- state ------------------------------------------------------------
    def kpis(self):
        ev = self.store.events; lv = self.store.counts_by_level(); resp = [e["resp"] for e in ev if e.get("resp") is not None]
        o = self.orch.n
        return dict(threats=sum(1 for e in ev if e["level"] > 0), handled=sum(1 for e in ev if e["status"] == "done"), missed=o["miss"], raw=o["raw"],
                    sent=sum(1 for e in ev if e["level"] > 0), filtered=o["sup"], false_dispatch=o["fp"], digest=sum(1 for e in ev if e["status"] == "logged"),
                    blocked=o["blocked"], avg_response=round(sum(resp) / len(resp), 1) if resp else None,
                    critical=lv[3], high=lv[2], medium=lv[1], low=lv[0], levels=lv,
                    cams_online=sum(1 for c in self.cams.values() if c.status in ("live", "paused", "ended")))

    def state(self):
        with self.lock:
            now = time.time(); self._mirror()
            for e in self.store.events:
                if e["level"] == 3 and e["status"] == "new" and not e["esc"] and now - e["ts"] > C.POLICY["escalate_after"]:
                    e["esc"] = True; self.store.save(e); self.say(f"#{e['id']} Critical alert unacknowledged: escalated to commander.")
            ev = [dict(e, time=dt.datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M:%S"), status_key=e["status"],
                       status=STATUS_NAMES.get(e["status"], e["status"])) for e in reversed(self.store.events[-300:])]
            ag = {}
            for a in self.orch.agents: ag[a.name] = ag.get(a.name, 0) + a.count
            for c in self.cams.values():
                if c.analyzer:
                    for a in c.analyzer.agents: ag[a.name] = ag.get(a.name, 0) + a.count
            ag["alert"] = ag.get("alert", 0) + self.video_alerts
            per = {}
            for e in self.store.events: per[e["cam"]] = per.get(e["cam"], 0) + 1
            cams = [dict(id=c.cam, sector=c.sector, status=c.status, name=c.name, fps=round(c.fps), proc_ms=round(c.proc_ms), events=per.get(c.cam, 0),
                         backend=c.analyzer.detector.backend if c.analyzer else None, zones=self.zones.get(c.cam, []), fence_y=self.fence.get(c.cam, .45))
                    for c in self.cams.values()]
            notes = sorted({c.analyzer.detector.note for c in self.cams.values() if c.analyzer and c.analyzer.detector.note})
            return dict(now=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), events=ev, kpi=self.kpis(), types=self.store.counts_by_type(),
                        timeline=self.store.timeline(), agents=ag, cams=cams,
                        log=[f"{dt.datetime.fromtimestamp(t):%H:%M:%S}  {m}" for t, m in list(self.log)[:60]],
                        cfg=self.cfg, tau=self.orch.tau, agents_on=self.orch.agents_on, night=self.world.night, bad=self.world.bad_weather,
                        video=V.AVAILABLE, backend=self.backend, notes=notes, model=self.model)

    def ask(self, q):
        with self.lock:
            return answer(q, self.store, self.kpis(), self.kpis()["cams_online"],
                          next((c.analyzer.detector.backend for c in self.cams.values() if c.analyzer), self.backend))

    def thumbs(self, n=12):
        import base64, cv2
        out = {}
        for e in [x for x in reversed(self.store.events) if x["snap"] and x["level"] >= 2][:n]:
            f = os.path.join(self.data, "evidence", f"{e['id']}.jpg")
            if os.path.exists(f):
                im = cv2.imread(f); im = cv2.resize(im, (320, int(im.shape[0] * 320 / im.shape[1])))
                out[e["id"]] = base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()).decode()
        return out

    def heat_jpeg(self, cam):
        import cv2
        c = self.cams.get(cam)
        if not c or c.analyzer is None or c.last_raw is None: return None
        return cv2.imencode(".jpg", c.analyzer.heat_overlay(c.last_raw, .6), [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes()
