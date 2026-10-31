import math
from .base import Agent
from .. import config as C

class BehaviourAgent(Agent):
    """Speed, dwell time and heading from the track history; flags loitering and groups."""
    name, outputs = "behaviour", frozenset({"speed", "dwell", "heading", "straight", "loiter_flag", "group_flag"})
    def process(self, track, ctx):
        p = track.pos
        speed = 0.0
        if len(p) >= 3:
            a, b = p[-3], p[-1]
            speed = math.hypot(b[1] - a[1], b[2] - a[2]) / max(b[0] - a[0], 1e-6)
        speed = .6 * speed + .4 * track.feats.get("speed", speed)
        dwell = track.feats.get("dwell", 0.0) + 0.5 if speed < 5 else 0.0
        heading = 0.0
        if len(p) >= 2:
            dy = p[-1][2] - p[-2][2]
            heading = 1.0 if (dy > 0 and p[-1][2] < C.FENCE_Y + 40) else (-1.0 if dy < 0 else 0.0)
        straight = 1.0
        if len(p) >= 5:
            path = sum(math.hypot(p[i + 1][1] - p[i][1], p[i + 1][2] - p[i][2]) for i in range(len(p) - 1))
            net = math.hypot(p[-1][1] - p[0][1], p[-1][2] - p[0][2])
            straight = net / path if path > 20 else 1.0       # near 1: purposeful, low: erratic
        dist = abs(p[-1][2] - C.FENCE_Y)
        loiter = dwell > 20 and dist < 100
        group = track.gs >= 3
        self.count += loiter or group
        return {"speed": speed, "dwell": dwell, "heading": heading, "straight": straight, "loiter_flag": loiter, "group_flag": group}
