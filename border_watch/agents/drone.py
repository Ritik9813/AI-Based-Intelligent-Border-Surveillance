from .base import Agent

class DroneAgent(Agent):
    """RF and radar drone detector."""
    name, outputs = "drone", frozenset({"drone_cue"})
    def process(self, track, ctx):
        cue = track.ev["rf"] > .4
        self.count += cue
        return {"drone_cue": cue}
