from .base import Agent
from .. import config as C
from ..events import Alert

class AlertAgent(Agent):
    """Creates alerts, chooses delivery channel by level, runs the escalation timer."""
    name, outputs = "alert", frozenset({"alert"})
    def __init__(self):
        super().__init__(); self.alerts = {}
    def process(self, track, ctx):
        return {}
    def raise_alert(self, track, lvl, t, top):
        a = Alert(id=track.id, t0=t, lvl=lvl, th=track.th, risk=track.risk, top=top,
                  channels=C.CHANNELS[lvl] if lvl != "U" else ["console"])
        self.alerts[a.id] = a; track.alert = a; self.count += 1
        return a
    def open_alerts(self):
        return [a for a in self.alerts.values() if a.status in ("new", "ack") and (a.lvl == "U" or a.lvl > 0)]
    def check_escalation(self, t):
        out = []
        for a in self.open_alerts():
            if a.lvl == 3 and a.status == "new" and not a.escalated and t - a.t0 > C.POLICY["escalate_after"]:
                a.escalated = True; out.append(a)
        return out
