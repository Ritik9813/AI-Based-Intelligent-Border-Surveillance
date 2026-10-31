from .base import Agent

class VehicleAgent(Agent):
    """Radar-based vehicle cue: strong radar return plus vehicle-like speed."""
    name, outputs = "vehicle", frozenset({"vehicle_cue"})
    def process(self, track, ctx):
        speed = track.feats.get("speed", 0)
        cue = track.ev["radar"] > .6 and speed > 30
        self.count += cue
        return {"vehicle_cue": cue}
