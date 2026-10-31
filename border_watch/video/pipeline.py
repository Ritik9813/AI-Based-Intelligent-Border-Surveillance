"""Video agents and the per-camera analyzer.
Vision -> Behaviour -> Perimeter / Vehicle / Drone -> Fusion -> Risk, then the engine's Alert agent and orchestrator.
Restricted zones are polygons (normalised 0..1) drawn by the operator; the default is everything below a fence line."""
import cv2, numpy as np
from ..agents.base import Agent
from .detector import Detector
from .tracker import Tracker

TYPES = ["Unauthorized Crossing", "Group Movement", "Vehicle Intrusion", "Drone Detection", "Loitering",
         "Fence Breach", "Abandoned Object"]
SEVERITY = {"Unauthorized Crossing": .60, "Group Movement": .65, "Vehicle Intrusion": .45, "Drone Detection": .75,
            "Loitering": .30, "Fence Breach": .45, "Abandoned Object": .70}
CUTS = (.45, .70, 1.00)
RED, AMBER = (59, 56, 229), (0, 190, 255)
LABEL_COLOR = {"person": (59, 56, 229), "vehicle": (0, 165, 255), "drone": (246, 92, 139), "object": (80, 200, 120)}

class ZoneSet:
    """Rasterised restricted zones for one frame size."""
    def __init__(self, W, H, polys=None, fence_y=.45):
        self.W, self.H = W, H
        self.polys = polys or [dict(name="Restricted zone", pts=[[0, fence_y], [1, fence_y], [1, 1], [0, 1]])]
        self.custom = bool(polys)
        m = np.zeros((H, W), np.uint8)
        for z in self.polys:
            cv2.fillPoly(m, [np.array([[int(x * (W - 1)), int(y * (H - 1))] for x, y in z["pts"]], np.int32)], 1)
        k = int(0.12 * min(W, H)) | 1
        self.mask, self.near = m, cv2.dilate(m, np.ones((k, k), np.uint8))
    def _pt(self, x, y): return min(max(int(y), 0), self.H - 1), min(max(int(x), 0), self.W - 1)
    def inside(self, x, y): return bool(self.mask[self._pt(x, y)])
    def is_near(self, x, y): return bool(self.near[self._pt(x, y)])
    def overlap(self, box):
        x1, y1, x2, y2 = [int(v) for v in box]; x1, x2 = max(0, x1), min(self.W, x2); y1, y2 = max(0, y1), min(self.H, y2)
        return float(self.mask[y1:y2, x1:x2].mean()) if x2 > x1 and y2 > y1 else 0.0

class VisionAgent(Agent):
    name, outputs = "vision", frozenset({"detections"})
    def __init__(self, detector): super().__init__(); self.det = detector
    def process(self, frame, ctx):
        d = self.det.detect(frame); self.count += len(d); return {"detections": d}

class BehaviourAgent(Agent):
    """Tracks objects; finds loitering and group movement."""
    name, outputs = "behaviour", frozenset({"tracks", "candidates"})
    def __init__(self, width, loiter_s=10.0): super().__init__(); self.tracker, self.loiter_s, self.last_group = Tracker(width), loiter_s, -99
    def process(self, ctx):
        tr = self.tracker.update(ctx["detections"], ctx["t"]); W, Z, c = ctx["W"], ctx["zones"], []
        pers = [x for x in tr if x.confirmed and x.label == "person" and ctx["t"] - x.last_t < 1.0]
        for p in pers:
            if Z.is_near(*p.foot) and p.dwell > self.loiter_s and "loiter" not in p.fired:
                p.fired.add("loiter"); c.append(dict(type="Loitering", tracks=[p], in_zone=Z.inside(*p.foot)))
        near = [p for p in pers if sum(abs(p.cx - q.cx) + abs(p.cy - q.cy) < .3 * W for q in pers) >= 3]
        if len(near) >= 3 and ctx["t"] - self.last_group > 20:
            self.last_group = ctx["t"]; c.append(dict(type="Group Movement", tracks=near, in_zone=any(Z.inside(*p.foot) for p in near)))
        self.count += len(c); return {"tracks": tr, "candidates": c}

class PerimeterAgent(Agent):
    """Restricted-zone entry, fence tampering and vehicle entry, using the drawn zones."""
    name, outputs = "perimeter", frozenset({"candidates"})
    def process(self, ctx):
        Z, t, dt, c = ctx["zones"], ctx["t"], ctx["dt"], []
        for x in ctx["tracks"]:
            if not x.confirmed or t - x.last_t > 1.0: continue
            inside = Z.inside(*x.foot)
            if inside: x.zone_time += dt
            else: x.seen_outside = True
            if x.label == "person":
                if x.zone_time >= .8 and "cross" not in x.fired:
                    x.fired.add("cross"); c.append(dict(type="Unauthorized Crossing", tracks=[x], in_zone=True, entered=x.seen_outside))
                ov = Z.overlap(x.box); straddle = .1 < ov < .9 and x.speed < .02
                x.edge_time = x.edge_time + dt if straddle else 0.0
                if x.edge_time > 2.0 and "breach" not in x.fired:
                    x.fired.add("breach"); c.append(dict(type="Fence Breach", tracks=[x], in_zone=True))
            elif x.label == "vehicle" and x.zone_time >= 1.0 and "veh" not in x.fired:
                x.fired.add("veh"); c.append(dict(type="Vehicle Intrusion", tracks=[x], in_zone=True))
            elif x.label == "object" and x.dwell > 20 and "obj" not in x.fired:
                x.fired.add("obj"); c.append(dict(type="Abandoned Object", tracks=[x], in_zone=inside))
        self.count += len(c); return {"candidates": c}

class DroneAgent(Agent):
    name, outputs = "drone", frozenset({"candidates"})
    def process(self, ctx):
        c = [dict(type="Drone Detection", tracks=[x], in_zone=False) for x in ctx["tracks"]
             if x.label == "drone" and x.confirmed and x.age > 1.0 and "drone" not in x.fired and not x.fired.add("drone")]
        self.count += len(c); return {"candidates": c}

class VehicleAgent(Agent):
    """Counts vehicles seen; the intrusion rule itself lives in the perimeter agent."""
    name, outputs = "vehicle", frozenset({"vehicles"})
    def process(self, ctx):
        n = sum(1 for x in ctx["tracks"] if x.label == "vehicle" and x.confirmed); self.count += n; return {"vehicles": n}

class FusionAgent(Agent):
    """Confidence = mean track confidence x persistence. Weak candidates are held back."""
    name, outputs = "fusion", frozenset({"confidence"})
    MIN_CONF = 0.40
    def process(self, cand, ctx):
        self.count += 1
        conf = sum(x.conf for x in cand["tracks"]) / len(cand["tracks"])
        conf *= min(1.0, .7 + .1 * min(3, cand["tracks"][0].age))
        return {"confidence": round(min(.99, conf), 2)}

class RiskAgent(Agent):
    """Risk = severity x (1 + 0.3 group of 4+ + 0.4 inside restricted zone + 0.2 low light)."""
    name, outputs = "risk", frozenset({"risk", "level"})
    def process(self, cand, ctx):
        self.count += 1
        n = len(cand["tracks"]) if cand["type"] == "Group Movement" else 1
        r = SEVERITY[cand["type"]] * (1 + .3 * (n >= 4) + .4 * bool(cand["in_zone"]) + .2 * bool(ctx["night"]))
        return {"risk": round(r, 2), "level": 0 if r < CUTS[0] else 1 if r < CUTS[1] else 2 if r < CUTS[2] else 3}

class Analyzer:
    """One per camera. Feed frames in order; returns the annotated frame and new events."""
    def __init__(self, shape, detector=None, fence_y=.45, polys=None, show_zone=True):
        self.H, self.W = shape[:2]; self.fence_y, self.show_zone = fence_y, show_zone
        self.show_trails = self.show_heat = False; self.enhance = True
        self.detector = detector or Detector()
        self.zones = ZoneSet(self.W, self.H, polys, fence_y)
        self.vision, self.vehicle, self.drone = VisionAgent(self.detector), VehicleAgent(), DroneAgent()
        self.perimeter, self.behaviour = PerimeterAgent(), BehaviourAgent(self.W)
        self.fusion, self.risk = FusionAgent(), RiskAgent()
        self.agents = [self.vision, self.behaviour, self.perimeter, self.vehicle, self.drone, self.fusion, self.risk]
        self.t_prev, self.night = None, False
        self.heat = np.zeros((max(1, self.H // 8), max(1, self.W // 8)), np.float32)
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

    def set_zones(self, polys, fence_y=None):
        if fence_y is not None: self.fence_y = fence_y
        self.zones = ZoneSet(self.W, self.H, polys or None, self.fence_y)

    def reset(self):
        self.behaviour = BehaviourAgent(self.W); self.agents[1] = self.behaviour; self.detector.reset(); self.t_prev = None

    def _enhanced(self, frame):
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB); lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def process(self, frame, t, detect=True):
        events = []
        self.detector.feed(frame)
        if detect:
            self.night = float(frame[::8, ::8].mean()) < 60
            ctx = dict(t=t, W=self.W, H=self.H, zones=self.zones, night=self.night, dt=(t - self.t_prev) if self.t_prev is not None else 0.0)
            self.t_prev = t
            ctx.update(self.vision.process(self._enhanced(frame) if (self.night and self.enhance) else frame, ctx))
            ctx.update(self.behaviour.process(ctx))
            cands = list(ctx["candidates"])
            for ag in (self.perimeter, self.drone): cands += ag.process(ctx)["candidates"]
            self.vehicle.process(ctx)
            self.heat *= 0.9995
            for x in ctx["tracks"]:
                if x.confirmed and t - x.last_t < 0.5:
                    fx, fy = x.foot; self.heat[min(self.heat.shape[0] - 1, max(0, fy // 8)), min(self.heat.shape[1] - 1, max(0, fx // 8))] += 1.0
            for c in cands:
                conf = self.fusion.process(c, ctx)["confidence"]
                if conf < FusionAgent.MIN_CONF: continue
                rk = self.risk.process(c, ctx)
                lab = c["tracks"][0].label.capitalize(); n = len(c["tracks"])
                events.append(dict(type=c["type"], conf=conf, risk=rk["risk"], level=rk["level"], in_zone=c["in_zone"],
                                   objects=f"{n} Persons" if n > 1 else lab, night=self.night, t=t))
        out = self.draw(frame)
        for ev in events: ev["frame"] = out.copy()
        return out, events

    def heat_overlay(self, frame, alpha=.55):
        h = cv2.GaussianBlur(self.heat, (0, 0), 2.0); m = float(h.max())
        if m <= 0: return frame.copy()
        n = np.clip(h / m, 0, 1); big = cv2.resize(n, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
        col = cv2.applyColorMap((big * 255).astype(np.uint8), cv2.COLORMAP_JET)
        a = (np.clip(big * 1.6, 0, 1) * alpha)[..., None]
        return (frame * (1 - a) + col * a).astype(np.uint8)

    def draw(self, frame):
        out = self.heat_overlay(frame) if self.show_heat else frame.copy()
        if self.show_zone:
            ov = out.copy()
            for z in self.zones.polys:
                pts = np.array([[int(x * (self.W - 1)), int(y * (self.H - 1))] for x, y in z["pts"]], np.int32)
                cv2.fillPoly(ov, [pts], (40, 40, 200)); cv2.polylines(out, [pts], True, AMBER, 1, cv2.LINE_AA)
            out = cv2.addWeighted(ov, .14, out, .86, 0)
        t = self.t_prev
        for tr in self.behaviour.tracker.tracks:
            if not tr.confirmed or (t is not None and t - tr.last_t > 0.8): continue
            col = LABEL_COLOR.get(tr.label, RED)
            if self.show_trails and len(tr.hist) > 1:
                pts = np.array([[int(h[1]), int(h[2])] for h in tr.hist[-25:]], np.int32); cv2.polylines(out, [pts], False, col, 2, cv2.LINE_AA)
            x1, y1, x2, y2 = tr.box; cv2.rectangle(out, (x1, y1), (x2, y2), col, 2)
            txt = f"{tr.label.capitalize()} {tr.conf:.2f}"; (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, .5, 1)
            cv2.rectangle(out, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, max(th + 8, y1)), col, -1)
            cv2.putText(out, txt, (x1 + 4, max(th + 3, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1, cv2.LINE_AA)
        return out
