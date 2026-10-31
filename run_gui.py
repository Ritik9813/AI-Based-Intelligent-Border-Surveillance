"""Start the Border Watch console.
   python run_gui.py [--port 8000] [--backend auto|onnx|yolo|motion] [--model path] [--host 127.0.0.1] [--no-login]"""
import argparse, webbrowser, threading
from border_watch.server import serve
p = argparse.ArgumentParser(); p.add_argument("--port", type=int, default=8000); p.add_argument("--seed", type=int)
p.add_argument("--backend", default="auto", choices=["auto", "onnx", "yolo", "motion"],
               help="auto = bundled YOLOX neural network (falls back to motion+HOG). yolo needs: pip install ultralytics")
p.add_argument("--model", default="", help="custom .onnx (YOLOX format, optional .names file beside it) or .pt for --backend yolo")
p.add_argument("--imgsz", type=int, help="network input size for a custom ONNX model (default 416, or 640 for yolox_s/m/l/x)")
p.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to allow other computers (plain HTTP, put it behind HTTPS)")
p.add_argument("--no-login", action="store_true", help="skip the login screen (single trusted machine only)")
a = p.parse_args()
threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{a.port}")).start()
serve(a.port, a.seed, "motion+hog" if a.backend == "motion" else a.backend, a.model, a.host, not a.no_login, a.imgsz)
