"""Create a small synthetic test clip (a walker crossing the fence line, a vehicle and a drone-like speck).
   python tools/make_test_video.py   ->  sample_videos/synthetic_border.mp4
Use real footage for real evaluation. This clip only checks that the pipeline works."""
import os, numpy as np, cv2
rng = np.random.default_rng(0); W, H, FPS = 640, 360, 25
bg = cv2.GaussianBlur((rng.integers(60, 120, (H, W, 1)) + np.zeros((H, W, 3))).astype(np.uint8), (5, 5), 0)
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_videos"); os.makedirs(out, exist_ok=True)
vw = cv2.VideoWriter(os.path.join(out, "synthetic_border.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
for i in range(260):
    f = bg.copy()
    if i >= 50:
        yy = min(int(40 + (i - 50) * 2.5), H - 82); f[yy:yy + 80, 200:232] = rng.integers(0, 90, (80, 32, 3)).astype(np.uint8)
    if i >= 60:
        x = int((40 + (i - 60) * 5) % 520); cv2.rectangle(f, (x, 250), (x + 110, 295), (200, 200, 200), -1)
        x = int((500 - (i - 60) * 3) % 600); cv2.rectangle(f, (x, 30), (x + 14, 40), (20, 20, 20), -1)
    vw.write(cv2.add(f, rng.integers(0, 4, f.shape, dtype=np.uint8)))
vw.release(); print("wrote", os.path.join(out, "synthetic_border.mp4"))
