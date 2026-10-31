# Models
`yolox_tiny.onnx` is the YOLOX-Tiny detector (COCO, 80 classes) from https://github.com/Megvii-BaseDetection/YOLOX (release 0.1.1rc0),
licensed Apache-2.0 (c) Megvii Inc. It is run by OpenCV, so no PyTorch is needed.

Use another YOLOX model: put e.g. `yolox_s.onnx` here and start with `python run_gui.py --model models/yolox_s.onnx` (input size 640 is picked
automatically for s/m/l/x). If the file is missing and you are online, it is downloaded from the YOLOX release.

Use your own model (for example one trained to detect drones): export it in YOLOX ONNX format, save a text file with the same name and a
`.names` extension (one class name per line, a name containing "drone" is treated as a drone), and pass `--model your_model.onnx --imgsz 640`.
