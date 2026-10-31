from .base import Agent

class VisionAgent(Agent):
    """Reads visible and thermal cameras. Smooths scores and counts blobs (group size)."""
    name, outputs = "vision", frozenset({"vision_conf", "blobs"})
    def process(self, track, ctx):
        self.count += 1
        return {"vision_conf": max(track.ev["cam"], track.ev["thermal"]), "blobs": track.gs}
