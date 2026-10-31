"""Object detection for uploaded video.
Backends:  'onnx'        YOLOX neural network run by OpenCV (bundled model, no PyTorch needed)  <- default
           'yolo'        Ultralytics YOLO (optional: pip install ultralytics)
           'motion+hog'  OpenCV people detector + background subtraction (heuristic fallback)
'auto' tries onnx, then falls back to motion+hog."""
import os, threading
from dataclasses import dataclass
import cv2, numpy as np

@dataclass
class Detection:
    label: str       # person, vehicle, drone, object
    conf: float
    box: tuple       # x1, y1, x2, y2

COCO_MAP = {"person": "person", "car": "vehicle", "truck": "vehicle", "bus": "vehicle", "motorcycle": "vehicle",
            "airplane": "drone", "kite": "drone", "bird": "drone",
            "backpack": "object", "suitcase": "object", "handbag": "object"}

COCO80 = ("person bicycle car motorcycle airplane bus train truck boat traffic_light fire_hydrant stop_sign parking_meter bench bird cat dog "
          "horse sheep cow elephant bear zebra giraffe backpack umbrella handbag tie suitcase frisbee skis snowboard sports_ball kite baseball_bat "
          "baseball_glove skateboard tennis_racket bottle wine_glass cup fork knife spoon bowl banana apple sandwich orange broccoli carrot hot_dog "
          "pizza donut cake chair couch potted_plant bed dining_table toilet tv laptop mouse remote keyboard cell_phone microwave oven toaster sink "
          "refrigerator book clock vase scissors teddy_bear hair_drier toothbrush").split()
MODELS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")
YOLOX_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/{}.onnx"

def map_label(name):
    """Map a model class name to one of our four labels (None = ignore).
    COCO has no drone class, so small aerial classes stand in; use a custom model with a 'drone' class for accuracy."""
    n = str(name).lower()
    if "drone" in n or "uav" in n: return "drone"
    return COCO_MAP.get(n)

class Detector:
    _yolo = {}; _lock = threading.Lock(); _nets = {}

    def __init__(self, backend="auto", model="", min_conf=0.35, imgsz=None):
        self.min_conf, self.note, self.backend, self.model_name = min_conf, "", None, model
        if backend in ("auto", "onnx"):
            try:
                path = model if model.endswith(".onnx") else os.path.join(MODELS, "yolox_tiny.onnx")
                if not os.path.exists(path):                        # first run on a machine without the bundled file
                    import urllib.request; os.makedirs(MODELS, exist_ok=True)
                    urllib.request.urlretrieve(YOLOX_URL.format(os.path.splitext(os.path.basename(path))[0]), path)
                with Detector._lock:
                    if path not in Detector._nets: Detector._nets[path] = cv2.dnn.readNetFromONNX(path)
                self.net, self.backend, self.model_name = Detector._nets[path], "onnx", os.path.basename(path)
                self.size = imgsz or (640 if any(k in path for k in ("yolox_s", "yolox_m", "yolox_l", "yolox_x")) else 416)
                names = path[:-5] + ".names"                          # optional custom class list, one name per line
                self.names = [l.strip() for l in open(names)] if os.path.exists(names) else COCO80
            except Exception as ex:
                if backend == "onnx": raise
                self.note = f"ONNX model unavailable ({type(ex).__name__}: {ex}); using fallback."
        if self.backend is None and backend in ("auto", "yolo") and backend == "yolo":
            try:
                with Detector._lock:
                    if model not in Detector._yolo:
                        from ultralytics import YOLO
                        Detector._yolo[model or "yolov8n.pt"] = YOLO(model or "yolov8n.pt")
                self.model, self.backend = Detector._yolo[model or "yolov8n.pt"], "yolo"
            except Exception as ex:
                raise RuntimeError(f"Ultralytics YOLO is not available: {ex}")
        if self.backend is None:
            self.backend = "motion+hog"
            self.hog = None                                           # OpenCV 5 moved the HOG people detector out of the main module
            if hasattr(cv2, "HOGDescriptor"):
                self.hog = cv2.HOGDescriptor(); self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            else: self.note = self.note or "HOG people detector unavailable in this OpenCV build; using motion only."
            self.bg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=True)
            self.n = 0; self.fg_raw = None

    def reset(self):
        if self.backend == "motion+hog":
            self.bg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=True); self.n = 0; self.fg_raw = None

    def feed(self, frame):
        """Call on every frame: keeps the background model current (cheap). Detection can then run less often."""
        if self.backend != "motion+hog": return
        h, w = frame.shape[:2]; sc = min(1.0, 640 / w)
        small = cv2.resize(frame, None, fx=sc, fy=sc) if sc < 1 else frame
        self.fg_raw = self.bg.apply(small); self.n += 1

    def detect(self, frame):
        if self.backend == "onnx": return self._onnx_detect(frame)
        return self._yolo_detect(frame) if self.backend == "yolo" else self._motion_detect(frame)

    def _onnx_detect(self, frame):
        """YOLOX: letterbox to size x size, decode the raw head output, class-wise score, NMS."""
        size, (h, w) = self.size, frame.shape[:2]; r = min(size / h, size / w); nh, nw = int(h * r), int(w * r)
        img = np.full((size, size, 3), 114, np.uint8); img[:nh, :nw] = cv2.resize(frame, (nw, nh))
        with Detector._lock:
            self.net.setInput(cv2.dnn.blobFromImage(img, 1.0, (size, size), swapRB=False)); out = self.net.forward()[0].copy()
        gr, st = [], []
        for s in (8, 16, 32):
            g = size // s; xv, yv = np.meshgrid(np.arange(g), np.arange(g)); gr.append(np.stack((xv, yv), 2).reshape(-1, 2)); st.append(np.full((g * g, 1), s))
        gr, st = np.concatenate(gr), np.concatenate(st)
        out[:, :2] = (out[:, :2] + gr) * st; out[:, 2:4] = np.exp(out[:, 2:4]) * st
        sc = out[:, 4:5] * out[:, 5:]; cls, conf = sc.argmax(1), sc.max(1)
        labs = [map_label(self.names[c]) if c < len(self.names) else None for c in cls]
        idx = [i for i in range(len(conf)) if conf[i] >= self.min_conf and labs[i]]
        if not idx: return []
        bx = [[int((out[i, 0] - out[i, 2] / 2) / r), int((out[i, 1] - out[i, 3] / 2) / r), int(out[i, 2] / r), int(out[i, 3] / r)] for i in idx]
        keep = cv2.dnn.NMSBoxes(bx, [float(conf[i]) for i in idx], self.min_conf, 0.45)
        res = []
        for k in np.array(keep).reshape(-1):
            x, y, bw, bh = bx[k]; i = idx[k]
            res.append(Detection(labs[i], float(conf[i]), (max(0, x), max(0, y), min(w - 1, x + bw), min(h - 1, y + bh))))
        return res

    def _yolo_detect(self, frame):
        with Detector._lock:
            res = self.model(frame, verbose=False, conf=self.min_conf)[0]
        out = []
        for b in res.boxes:
            lab = map_label(self.model.names[int(b.cls[0])])
            if lab:
                x1, y1, x2, y2 = [int(v) for v in b.xyxy[0].tolist()]
                out.append(Detection(lab, float(b.conf[0]), (x1, y1, x2, y2)))
        return out

    def _motion_detect(self, frame):
        h, w = frame.shape[:2]; sc = min(1.0, 640 / w)
        small = cv2.resize(frame, None, fx=sc, fy=sc) if sc < 1 else frame
        sh, sw = small.shape[:2]
        if getattr(self, "fg_raw", None) is None or self.fg_raw.shape[:2] != (sh, sw): self.feed(frame)
        fg = self.fg_raw
        if self.n < 25: return []                                 # background model warm-up
        _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)    # drops shadow pixels (value 127)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        fg = cv2.dilate(fg, np.ones((7, 7), np.uint8), iterations=2)
        cnts, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        blobs = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > 0.0006 * sw * sh]
        rects, wts = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.08) if self.hog is not None else ((), ())
        out, taken = [], []
        for (x, y, bw, bh), wt in zip(rects, np.ravel(wts) if len(rects) else []):
            if wt < 0.35: continue
            moving = fg[y:y + bh, x:x + bw].mean() / 255.0
            if moving < 0.04 and wt < 0.9: continue               # static look-alikes (posts, trees)
            out.append(Detection("person", float(min(.99, .5 + .25 * wt)), (x, y, x + bw, y + bh))); taken.append((x, y, bw, bh))
        for (x, y, bw, bh) in blobs:
            if any(self._inter(x, y, bw, bh, *t) > .3 for t in taken): continue
            a, cy = bw * bh / (sw * sh), y + bh / 2
            if cy < .3 * sh and a < .01: lab, c = "drone", .5
            elif bw / bh > 1.3 and a > .015: lab, c = "vehicle", .6
            elif bh / bw > 1.4 and .002 < a < .08: lab, c = "person", .5
            else: continue
            out.append(Detection(lab, c, (x, y, x + bw, y + bh)))
        k = 1 / sc
        return [Detection(d.label, d.conf, tuple(int(v * k) for v in d.box)) for d in out]

    @staticmethod
    def _inter(x, y, w, h, X, Y, W, H):
        ix = max(0, min(x + w, X + W) - max(x, X)); iy = max(0, min(y + h, Y + H) - max(y, Y))
        return ix * iy / max(1, min(w * h, W * H))
