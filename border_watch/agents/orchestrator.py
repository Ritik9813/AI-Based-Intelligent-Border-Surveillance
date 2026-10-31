"""Orchestrator: the single control point. Routes data between agents, enforces the tool
allow-list, applies the escalation policy, requires human approval, keeps the audit log and
falls back to raw alarms if an agent fails."""
from .. import config as C
from ..events import Track
from .vision import VisionAgent
from .vehicle import VehicleAgent
from .drone import DroneAgent
from .perimeter import PerimeterAgent
from .behaviour import BehaviourAgent
from .fusion import FusionAgent
from .risk import RiskAgent
from .alert import AlertAgent

class Orchestrator:
    name = "orchestrator"
    def __init__(self, world):
        self.world = world
        self.vision, self.vehicle, self.drone = VisionAgent(), VehicleAgent(), DroneAgent()
        self.perimeter, self.behaviour = PerimeterAgent(), BehaviourAgent()
        self.fusion, self.risk, self.alert = FusionAgent(), RiskAgent(), AlertAgent()
        self.agents = [self.vision, self.vehicle, self.drone, self.perimeter, self.behaviour,
                       self.fusion, self.risk, self.alert]
        self.tracks, self.log, self.feedback = {}, [], []
        self.agents_on, self.failsafe = True, False
        self.tau = C.POLICY["tau"]
        self.n = dict(raw=0, op=0, hit=0, miss=0, sup=0, fp=0, dig=0, blocked=0)
        self.resp = []

    # ---- control layer -------------------------------------------------
    def say(self, msg):
        self.log.insert(0, (round(self.world.t, 1), msg)); del self.log[80:]

    def request_tool(self, agent, tool, approved=False):
        """Check a tool call against the allow-list and the human-approval rule."""
        if tool not in C.TOOL_ALLOWLIST.get(agent, set()):
            self.n["blocked"] += 1; self.say(f"BLOCKED: {agent} may not use {tool}.")
            raise PermissionError(f"{agent} may not use {tool}")
        if tool in C.NEEDS_HUMAN_APPROVAL and not approved:
            self.n["blocked"] += 1; self.say(f"BLOCKED: {tool} needs operator approval.")
            raise PermissionError(f"{tool} needs operator approval")
        return True

    def _run(self, agent, track, ctx):
        out = agent.process(track, ctx)
        bad = set(out) - set(agent.outputs)
        if bad:                                  # schema check: agents cannot return undeclared keys
            self.say(f"BLOCKED: {agent.name} returned undeclared fields {sorted(bad)}.")
            out = {k: v for k, v in out.items() if k in agent.outputs}
        return out

    # ---- pipeline ------------------------------------------------------
    def step(self, dt=0.1):
        obs, done = self.world.step(dt)
        for e, rd in obs: self.ingest(e.id, rd)
        for e in done: self.finish(e.id)
        for a in self.alert.check_escalation(self.world.t):
            self.say(f"#{a.id} Critical alert unacknowledged for {C.POLICY['escalate_after']:.0f} s: escalated to commander.")

    def ingest(self, tid, rd):
        tr = self.tracks.setdefault(tid, Track(tid))
        tr.obs += 1; tr.gs, tr.auth = rd["gs"], rd["auth"]
        tr.pos.append((rd["t"], rd["x"], rd["y"])); tr.pos = tr.pos[-6:]
        for name, v in rd["readings"].items():
            if v is None: tr.cov[name] = False; continue
            tr.ev[name] = v if not tr.cov[name] and tr.obs == 1 else tr.ev[name] * .7 + v * .3
            tr.cov[name] = True
        ctx = dict(night=self.world.night, bad=self.world.bad_weather)
        try:
            for ag in (self.vision, self.behaviour, self.vehicle, self.drone, self.perimeter):
                tr.feats.update(self._run(ag, tr, ctx))
            if not tr.raw and max(tr.ev[k] for k in C.SENSORS if tr.cov[k]) > .6:
                tr.raw = True; self.n["raw"] += 1
                if not self.agents_on or self.failsafe: self._raw_alarm(tr)
            if tr.obs < C.POLICY["min_obs"] or not self.agents_on or self.failsafe or tr.closed:
                return
            f = self._run(self.fusion, tr, ctx); tr.post, tr.th = f["posterior"], f["threat_prob"]
            r = self._run(self.risk, tr, ctx); tr.risk, tr.lvl = r["risk"], r["level"]
        except Exception as ex:                  # fail-safe: never silence a sensor
            self.failsafe = True; self.say(f"FAIL-SAFE: {type(ex).__name__} in pipeline. Reverting to raw alarms.")
            self._raw_alarm(tr); return
        self._decide(tr)

    def _corroborated(self, tr):
        """Low-confidence events need two independent sensors above 0.4."""
        return tr.th >= C.POLICY["strong_threat"] or sum(tr.ev[k] > .4 for k in C.SENSORS if tr.cov[k]) >= 2

    def _decide(self, tr):
        top = max(range(len(tr.post)), key=tr.post.__getitem__)
        a = tr.alert
        if a is None and tr.th >= self.tau and self._corroborated(tr):
            a = self.alert.raise_alert(tr, tr.lvl, self.world.t, top)
            if a.lvl > 0: self.n["op"] += 1
            self.say(f"#{tr.id} alert: {C.LEVELS[a.lvl]} risk, {C.NAMES[top]} ({tr.th:.0%} threat). Channels: {', '.join(a.channels)}.")
        elif a and a.lvl != "U" and a.status == "new":
            if a.lvl == 0 and tr.lvl > 0: self.n["op"] += 1
            a.lvl, a.th, a.risk, a.top = tr.lvl, tr.th, tr.risk, top
            if tr.th < self.tau - .25 and self.world.t - a.t0 < 10:   # only young alerts can be withdrawn
                a.status = "withdrawn"; tr.closed = True
                if a.lvl > 0: self.n["op"] -= 1
                self.say(f"#{tr.id} withdrawn after re-evaluation.")
        elif a and a.status == "ack":
            a.th, a.risk, a.top = tr.th, tr.risk, top

    def _raw_alarm(self, tr):
        if tr.alert: return
        self.alert.raise_alert(tr, "U", self.world.t, 0); self.n["op"] += 1
        self.say(f"#{tr.id} raw sensor alarm (unranked).")

    def finish(self, tid):
        tr = self.tracks.get(tid); cls = self.world.truth[tid]; a = tr.alert if tr else None
        if a and a.status in ("new", "ack"):
            if a.lvl == 0:
                a.status = "digest"; self.n["dig"] += 1; self.n["hit"] += cls < C.N_THREAT
            else:
                a.status = "lost"
                if cls < C.N_THREAT:
                    self.n["miss"] += 1; self.say(f"#{tid} {C.NAMES[cls]} left the sector without a response.")
        elif not a and cls < C.N_THREAT and not (tr and tr.closed):
            self.n["miss"] += 1; self.say(f"#{tid} {C.NAMES[cls]} was never alerted (missed).")
        elif not a and tr and tr.raw and cls >= C.N_THREAT:
            self.n["sup"] += 1

    # ---- human operator -----------------------------------------------
    def operator(self, tid, action):
        a = self.alert.alerts.get(tid)
        if not a or a.status not in ("new", "ack"): return False, "Alert is not open."
        cls = self.world.truth[tid]; t = self.world.t
        if action == "ack":
            a.status, a.t_ack = "ack", t; self.say(f"Operator acknowledged #{tid}."); return True, "Acknowledged."
        if action == "go":
            if a.lvl != "U" and a.lvl >= 2 and a.status != "ack":
                self.n["blocked"] += 1; self.say(f"BLOCKED: #{tid} needs acknowledgement before dispatch.")
                return False, "Policy: acknowledge High and Critical alerts before dispatching."
            self.request_tool("orchestrator", "dispatch_response", approved=True)
            a.status = "done"
            if cls < C.N_THREAT:
                self.n["hit"] += 1; self.resp.append(t - a.t0)
                self.say(f"Response dispatched to #{tid} after {t - a.t0:.0f} s. Confirmed: {C.NAMES[cls]}.")
            else:
                self.n["fp"] += 1; self.say(f"Response dispatched to #{tid}: false alarm ({C.NAMES[cls]}). Label saved.")
        elif action == "no":
            a.status = "done"
            if cls >= C.N_THREAT: self.say(f"#{tid} dismissed correctly ({C.NAMES[cls]}). Label saved.")
            else: self.n["miss"] += 1; self.say(f"#{tid} dismissed but was a real {C.NAMES[cls]}. Flagged for review.")
        else: return False, "Unknown action."
        tr = self.tracks[tid]; tr.closed = True
        self.feedback.append(dict(id=tid, true_class=C.CLASSES[cls], predicted=C.CLASSES[a.top], action=action,
                                  **{k: round(v, 3) for k, v in tr.ev.items()}, speed=round(tr.feats.get("speed", 0), 1), group=tr.gs))
        return True, "Done."

    # ---- reporting -----------------------------------------------------
    def kpis(self):
        n = self.n
        return dict(threats=self.world.n_threats, handled=n["hit"], missed=n["miss"], raw=n["raw"], sent=n["op"],
                    filtered=n["sup"], false_dispatch=n["fp"], digest=n["dig"], blocked=n["blocked"],
                    avg_response=round(sum(self.resp) / len(self.resp), 1) if self.resp else None)
