import os
import cv2
import json
import subprocess
from typing import Dict, Any, Optional
from core.config import FFMPEG_EXE

def probe_video(file_path: str) -> Dict[str, Any]:
    """
    Extract video metadata (resolution, fps, duration, frame count, audio presence).
    Uses cv2.VideoCapture with ffprobe fallback/enhancement.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    info: Dict[str, Any] = {
        "file_path": os.path.abspath(file_path),
        "file_name": os.path.basename(file_path),
        "file_size_bytes": os.path.getsize(file_path),
        "width": 0,
        "height": 0,
        "fps": 30.0,
        "total_frames": 0,
        "duration_sec": 0.0,
        "duration_ms": 0,
        "has_audio": False,
        "video_codec": "unknown"
    }

    # 1. OpenCV probe
    cap = cv2.VideoCapture(file_path)
    if cap.isOpened():
        info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        info["fps"] = fps if fps and fps > 0 else 30.0
        info["total_frames"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if info["fps"] > 0 and info["total_frames"] > 0:
            info["duration_sec"] = info["total_frames"] / info["fps"]
            info["duration_ms"] = int(info["duration_sec"] * 1000)
        cap.release()

    # 2. FFprobe check for audio & codec
    ffprobe_exe = FFMPEG_EXE.replace("ffmpeg", "ffprobe") if "ffmpeg" in FFMPEG_EXE else "ffprobe"
    if not os.path.exists(ffprobe_exe):
        # try checking with ffmpeg itself
        ffprobe_exe = FFMPEG_EXE

    try:
        cmd = [
            FFMPEG_EXE,
            "-i", file_path,
            "-hide_banner"
        ]
        res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, errors="ignore")
        output = res.stderr
        
        # Parse Duration from stderr as fallback for VFR or missing headers
        import re
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
        if dur_match:
            hh, mm, ss = dur_match.groups()
            ffmpeg_dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
            if info["duration_sec"] <= 0.0 or info["total_frames"] <= 0:
                info["duration_sec"] = ffmpeg_dur
                info["duration_ms"] = int(ffmpeg_dur * 1000)
                if info["fps"] > 0:
                    info["total_frames"] = int(ffmpeg_dur * info["fps"])

        if "Audio:" in output:
            info["has_audio"] = True
        if "Video: h264" in output:
            info["video_codec"] = "h264"
        elif "Video: hevc" in output or "Video: h265" in output:
            info["video_codec"] = "hevc"
        elif "Video: vp9" in output:
            info["video_codec"] = "vp9"
        elif "Video: av1" in output:
            info["video_codec"] = "av1"
    except Exception:
        pass

    return info
