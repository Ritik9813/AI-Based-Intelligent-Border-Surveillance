from .base import Agent
from .. import config as C

class RiskAgent(Agent):
    """Risk = probability-weighted class severity x (1 + 0.3 group + 0.4 near fence + 0.2 night)."""
    name, outputs = "risk", frozenset({"risk", "level"})
    def process(self, track, ctx):
        self.count += 1
        P = track.post
        th = sum(P[:C.N_THREAT])
        sev = sum(P[c] * C.SEVERITY[c] for c in range(C.N_THREAT)) / max(th, 1e-9)
        mod = 1 + .3 * (track.gs >= 4) + .4 * (track.feats.get("dist_fence", 999) < 100) + .2 * ctx["night"]
        r = sev * mod
        a, b, c3 = C.RISK_CUTS
        return {"risk": r, "level": 0 if r < a else 1 if r < b else 2 if r < c3 else 3}
