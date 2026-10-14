import os
import sys
import shutil
import imageio_ffmpeg

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
JOBS_DIR = os.path.join(STORAGE_DIR, "jobs")

YOLO_MODEL_PATH = os.path.join(MODELS_DIR, "yolov8n.onnx")

def get_ffmpeg_path() -> str:
    """Find system ffmpeg or fallback to imageio_ffmpeg bundled binary."""
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        bin_dir = os.path.dirname(exe)
        standard_ffmpeg = os.path.join(bin_dir, "ffmpeg.exe")
        if not os.path.exists(standard_ffmpeg):
            try:
                shutil.copy2(exe, standard_ffmpeg)
            except Exception:
                pass
        if os.path.exists(standard_ffmpeg):
            exe = standard_ffmpeg
        if bin_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        return exe
    except Exception:
        return "ffmpeg"

FFMPEG_EXE = get_ffmpeg_path()

# Pipeline configuration
DEFAULT_SCAN_FPS = 8.0          # Sampling rate for Fast Lane (6~10 fps for continuous dance tracking)
DETECTOR_INPUT_SIZE = (640, 640) # Standard input size for YOLOv8 ONNX
DETECTOR_CONF_THRESH = 0.30
NMS_IOU_THRESH = 0.45

# Target Fancam aspect ratio 9:16
FANCAM_ASPECT_RATIO = 9 / 16
EXPORT_WIDTH = 720
EXPORT_HEIGHT = 1280

# Color and fallback settings
FALLBACK_POLICY = "HOLD_LAST_POSITION_AND_GLIDE"
