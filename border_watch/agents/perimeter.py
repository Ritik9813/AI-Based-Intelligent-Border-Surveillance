import math
from .base import Agent
from .. import config as C

class PerimeterAgent(Agent):
    """Fence vibration, gate and restricted-zone monitoring."""
    name, outputs = "perimeter", frozenset({"fence_cue", "dist_fence", "in_restricted"})
    def process(self, track, ctx):
        _, x, y = track.pos[-1]
        cue = track.ev["fence"] > .5
        self.count += cue
        return {"fence_cue": cue, "dist_fence": abs(y - C.FENCE_Y), "in_restricted": C.FENCE_Y <= y <= C.FENCE_Y + 70}
