"""Multi-object tracker: constant-velocity prediction, overlap + distance matching."""
import math
from collections import Counter

def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy; u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / u if u > 0 else 0.0

class Track:
    def __init__(self, id, det, t):
        self.id, self.box, self.conf, self.hits, self.first_t, self.last_t = id, det.box, det.conf, 1, t, t
        self.labels = Counter({det.label: 1}); self.hist = [(t, *self.center)]
        self.speed, self.dwell, self.fired = 0.0, 0.0, set()
        self.vx = self.vy = 0.0                                   # pixels per second
        self.zone_time = self.edge_time = 0.0; self.seen_outside = False
    @property
    def label(self): return self.labels.most_common(1)[0][0]
    @property
    def center(self): return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)
    @property
    def cx(self): return self.center[0]
    @property
    def cy(self): return self.center[1]
    @property
    def foot(self): return ((self.box[0] + self.box[2]) // 2, self.box[3])
    @property
    def confirmed(self): return self.hits >= 3
    @property
    def age(self): return self.last_t - self.first_t
    def predict(self, t):
        d = min(1.0, max(0.0, t - self.last_t)); dx, dy = self.vx * d, self.vy * d
        b = self.box; return (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)

class Tracker:
    def __init__(self, width, max_gap=2.0):
        self.W, self.max_gap, self.tracks, self.next_id, self.t_prev = width, max_gap, [], 1, None

    def update(self, dets, t):
        dt = (t - self.t_prev) if self.t_prev is not None else 0.0; self.t_prev = t
        free = list(range(len(dets)))
        for tr in sorted(self.tracks, key=lambda x: -x.hits):
            pb = tr.predict(t); pc = ((pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2); best, bs = None, 0.0
            for i in free:
                d = dets[i]
                if d.label != tr.label: continue
                dc = ((d.box[0] + d.box[2]) / 2, (d.box[1] + d.box[3]) / 2)
                dist = min(math.hypot(pc[0] - dc[0], pc[1] - dc[1]), math.hypot(tr.cx - dc[0], tr.cy - dc[1])) / self.W   # predicted or last position
                ov = max(iou(pb, d.box), iou(tr.box, d.box)); s = ov + (0.3 if dist < 0.1 else 0)
                if (ov > 0.1 or dist < 0.1) and s > bs: best, bs = i, s
            if best is not None:
                d = dets[best]; free.remove(best)
                move = math.hypot((d.box[0] + d.box[2]) / 2 - tr.cx, (d.box[1] + d.box[3]) / 2 - tr.cy)
                a = 0.6 if move < 0.5 * max(1, d.box[2] - d.box[0]) else 0.95            # smooth jitter, but follow fast movers closely
                tr.box = tuple(int(a * n + (1 - a) * o) for n, o in zip(d.box, tr.box))
                tr.conf = .7 * tr.conf + .3 * d.conf; tr.hits += 1; tr.last_t = t; tr.labels[d.label] += 1
                tr.hist.append((t, (d.box[0] + d.box[2]) / 2, (d.box[1] + d.box[3]) / 2)); tr.hist = tr.hist[-40:]
                old = next((h for h in tr.hist if t - h[0] >= 1.0), None)
                ref = tr.hist[0] if old is None else old; span = max(t - ref[0], 1e-6)
                if span >= 0.5:
                    tr.vx, tr.vy = (tr.hist[-1][1] - ref[1]) / span, (tr.hist[-1][2] - ref[2]) / span
                    tr.speed = math.hypot(tr.vx, tr.vy) / self.W
                tr.dwell = tr.dwell + dt if tr.speed < 0.015 else 0.0
        for i in free:
            self.tracks.append(Track(self.next_id, dets[i], t)); self.next_id += 1
        self.tracks = [tr for tr in self.tracks if t - tr.last_t <= self.max_gap]
        return self.tracks
