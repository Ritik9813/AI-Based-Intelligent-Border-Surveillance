import unittest, sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from border_watch.video.detector import map_label
from border_watch.video.tracker import Tracker
from border_watch.video.detector import Detection, Detector
from border_watch.video.pipeline import Analyzer, RiskAgent
from border_watch.store import EventStore, answer

class V(unittest.TestCase):
    def test_label_mapping(self):
        self.assertEqual(map_label("person"), "person"); self.assertEqual(map_label("truck"), "vehicle")
        self.assertEqual(map_label("my_drone_v2"), "drone"); self.assertEqual(map_label("backpack"), "object"); self.assertIsNone(map_label("cat"))
    def test_tracker_keeps_identity(self):
        tr = Tracker(640); ids = set()
        for i in range(10):
            ts = tr.update([Detection("person", .9, (100 + 4 * i, 100, 140 + 4 * i, 180))], i * .2); ids |= {t.id for t in ts}
        self.assertEqual(len(ids), 1); self.assertTrue(ts[0].confirmed)
    def test_risk_rules(self):
        r = RiskAgent(); T = type("T", (), {})
        one = [T()]; grp = [T() for _ in range(5)]
        a = r.process(dict(type="Group Movement", tracks=grp, in_zone=True), dict(night=False))
        b = r.process(dict(type="Loitering", tracks=one, in_zone=False), dict(night=False))
        self.assertEqual(a["level"], 3); self.assertEqual(b["level"], 0)
    def test_synthetic_clip_produces_events(self):
        import cv2
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_videos", "synthetic_border.mp4")
        cap = cv2.VideoCapture(path); ok, f = cap.read(); an = Analyzer(f.shape, Detector('motion+hog'), fence_y=.45); evs = []; i = 0
        while ok:
            _, e = an.process(f, i / 25.0, detect=(i % 4 == 0)); evs += e; ok, f = cap.read(); i += 1
        types = {e["type"] for e in evs}
        self.assertIn("Unauthorized Crossing", types); self.assertIn("Vehicle Intrusion", types); self.assertIn("Drone Detection", types)
    def test_assistant_and_store(self):
        s = EventStore(); s.add(cam="CAM-01", sector="North Sector", type="Drone Detection", objects="Drone", level=2, conf=.9, risk=.8)
        self.assertIn("1 open high-risk", answer("show high risk events", s, {}, 1, "x")); self.assertIn("Drone Detection", s.csv())
if __name__ == "__main__": unittest.main()
