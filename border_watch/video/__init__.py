"""Video analysis: detection, tracking and the video agents. Needs opencv-python-headless."""
try:
    import cv2  # noqa: F401
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
