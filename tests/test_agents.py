import unittest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from border_watch import config as C
from border_watch.events import Track
from border_watch.simulator import World
from border_watch.agents import Orchestrator, FusionAgent, RiskAgent, BehaviourAgent, VisionAgent

def mk(ev, speed, gs=1, auth=False, dist=100):
    t = Track(1, obs=6); t.ev.update(ev); t.cov = {k: True for k in t.cov}
    t.feats = dict(speed=speed, dist_fence=dist); t.gs, t.auth = gs, auth; return t
CTX = dict(night=False, bad=False)

class T(unittest.TestCase):
    def test_fusion_identifies_drone(self):
        t = mk(dict(cam=.35, thermal=.4, radar=.55, fence=0, rf=.85), 40)
        P = FusionAgent().posterior(t, CTX); self.assertEqual(P.index(max(P)), 4)
    def test_authorised_patrol_is_not_a_threat(self):
        t = mk(dict(cam=.8, thermal=.8, radar=.7, fence=.15, rf=0), 45, auth=True)
        self.assertLess(sum(FusionAgent().posterior(t, CTX)[:7]), .2)
    def test_animal_is_benign(self):
        t = mk(dict(cam=.45, thermal=.6, radar=.5, fence=.25, rf=0), 22)
        self.assertLess(sum(FusionAgent().posterior(t, CTX)[:7]), .3)
    def test_risk_levels_rise_with_group_and_proximity(self):
        P = [0] * 10; P[1] = 1.0
        a = mk({}, 12, gs=5, dist=50); a.post = P; b = mk({}, 12, gs=3, dist=300); b.post = P
        ra, rb = RiskAgent().process(a, CTX), RiskAgent().process(b, CTX)
        self.assertGreater(ra["risk"], rb["risk"]); self.assertEqual(ra["level"], 3)
    def test_agent_cannot_use_forbidden_tool(self):
        o = Orchestrator(World(1))
        with self.assertRaises(PermissionError): o.request_tool("vision", "dispatch_response")
        with self.assertRaises(PermissionError): o.request_tool("orchestrator", "dispatch_response")  # no approval
        self.assertTrue(o.request_tool("orchestrator", "dispatch_response", approved=True))
    def test_high_risk_requires_acknowledgement(self):
        w = World(2); w.auto = False; o = Orchestrator(w); w.spawn(3)
        for _ in range(400):
            o.step(0.1)
            if o.alert.open_alerts(): break
        a = o.alert.open_alerts()[0]
        if a.lvl != "U" and a.lvl >= 2:
            ok, _ = o.operator(a.id, "go"); self.assertFalse(ok)
            self.assertTrue(o.operator(a.id, "ack")[0]); self.assertTrue(o.operator(a.id, "go")[0])
    def test_failsafe_reverts_to_raw_alarms(self):
        w = World(3); w.auto = False; o = Orchestrator(w)
        o.fusion.process = lambda *a, **k: 1 / 0
        w.spawn(3)
        for _ in range(300): o.step(0.1)
        self.assertTrue(o.failsafe); self.assertTrue(any(a.lvl == "U" for a in o.alert.alerts.values()))
    def test_agents_cut_operator_load(self):
        res = {}
        for on in (False, True):
            w = World(5); o = Orchestrator(w); o.agents_on = on
            for _ in range(36000): o.step(0.1)
            res[on] = o.n["op"]
        self.assertLess(res[True], res[False] * 0.5)
if __name__ == "__main__": unittest.main()
