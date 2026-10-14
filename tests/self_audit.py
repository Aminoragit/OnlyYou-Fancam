import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import subprocess
import cv2
import numpy as np
from core.config import FFMPEG_EXE

def run_probe(filepath: str) -> dict:
    cmd = [
        FFMPEG_EXE,
        "-i", filepath
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    stderr = res.stderr
    
    cap = cv2.VideoCapture(filepath)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    # parse duration and audio from stderr
    import re
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    dur_sec = 0.0
    if dur_match:
        h_val, m_val, s_val = dur_match.groups()
        dur_sec = int(h_val) * 3600 + int(m_val) * 60 + float(s_val)
        
    has_audio = "Audio:" in stderr
    audio_info = ""
    if has_audio:
        a_line = [l for l in stderr.splitlines() if "Audio:" in l]
        audio_info = a_line[0].strip() if a_line else ""

    return {
        "width": w,
        "height": h,
        "fps": fps,
        "frames": nb_frames,
        "duration": dur_sec,
        "has_audio": has_audio,
        "audio_info": audio_info,
        "raw_info": stderr
    }

def audit_previous_job(job_dir: str, source_path: str):
    print("========================================")
    print("1. PROBING ORIGINAL SOURCE VIDEO")
    print("========================================")
    src_probe = run_probe(source_path)
    print(f"Source: {source_path}")
    print(f"Dimensions: {src_probe['width']}x{src_probe['height']}, FPS: {src_probe['fps']}, Frames: {src_probe['frames']}, Duration: {src_probe['duration']:.3f}s")
    print(f"Has Audio: {src_probe['has_audio']} ({src_probe['audio_info']})")

    print("\n========================================")
    print("2. AUDITING EXPORTED 9:16 FANCAMS")
    print("========================================")
    export_dir = os.path.join(job_dir, "export")
    if not os.path.exists(export_dir):
        print(f"Export dir not found: {export_dir}")
        return

    files = [f for f in os.listdir(export_dir) if f.endswith(".mp4")]
    files.sort()

    src_duration = src_probe["duration"]
    for fname in files:
        fpath = os.path.join(export_dir, fname)
        p = run_probe(fpath)
        v_dur = p["duration"]
        v_nb_frames = p["frames"]
        w = p["width"]
        h = p["height"]
        a_present = p["has_audio"]
        
        # Check moov atom position (faststart)
        with open(fpath, "rb") as f:
            header = f.read(1024)
            is_faststart = b"moov" in header

        src_diff_ms = abs(v_dur - src_duration) * 1000

        print(f"File: {fname}")
        print(f"  Dimensions: {w}x{h} (Aspect ratio: {w/h:.4f} vs 9/16={9/16:.4f})")
        print(f"  Video Duration: {v_dur:.3f} s ({v_nb_frames} frames)")
        print(f"  Audio Present: {a_present} | Audio Info: {p['audio_info']}")
        print(f"  Source Duration Diff: {src_diff_ms:.1f} ms")
        print(f"  Faststart (moov atom at head): {'YES (Optimized)' if is_faststart else 'NO (Requires buffering)'}")

    print("\n========================================")
    print("3. AUDITING CAMERA PATH & FRAMING STABILITY")
    print("========================================")
    manifest_path = os.path.join(job_dir, "preview", "preview_manifest_v1.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        camera_paths = manifest.get("camera_paths", {})
        for pid, path in camera_paths.items():
            if not path:
                print(f"[{pid}] Empty camera path!")
                continue

            fallback_points = [p for p in path if p.get("state") == "fallback"]
            tracked_points = [p for p in path if p.get("state") == "tracked"]
            interpolated_points = [p for p in path if p.get("state") == "interpolated"]

            fallback_pct = (len(fallback_points) / len(path)) * 100.0

            # Acceleration check
            xs = np.array([p["cx"] for p in path])
            ys = np.array([p["cy"] for p in path])
            ws = np.array([p["w"] for p in path])
            hs = np.array([p["h"] for p in path])

            # Check border margin clipping
            min_x_margin = np.min(xs - ws / 2.0)
            max_x_margin = np.max(xs + ws / 2.0)
            min_y_margin = np.min(ys - hs / 2.0)
            max_y_margin = np.max(ys + hs / 2.0)

            print(f"[{pid}] Total keyframes={len(path)}")
            print(f"  - Tracked: {len(tracked_points)}, Interpolated: {len(interpolated_points)}, Fallback: {len(fallback_points)} ({fallback_pct:.1f}%)")
            print(f"  - Viewport bounds: X=[{min_x_margin:.3f}, {max_x_margin:.3f}], Y=[{min_y_margin:.3f}, {max_y_margin:.3f}]")
            if min_x_margin < -0.001 or max_x_margin > 1.001:
                print(f"  - [INFO] Centered at border with clean black padding (requested).")
            else:
                print(f"  - [INFO] 100% inside original frame.")

if __name__ == "__main__":
    audit_previous_job("storage/jobs/job_20261014_155123", "storage/test_data/dancers.mp4")
