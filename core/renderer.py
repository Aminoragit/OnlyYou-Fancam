import os
import sys
import subprocess
import cv2
import numpy as np
from typing import List, Dict, Any, Callable, Optional, Tuple
from core.config import FFMPEG_EXE, EXPORT_WIDTH, EXPORT_HEIGHT

def interpolate_camera_roi(path_points: List[Dict[str, Any]], t_ms: int) -> Tuple[float, float, float, float, str, float]:
    """
    Interpolate (cx, cy, w, h, state, blend_factor) at time t_ms from sorted path points
    using continuous Hermite smoothstep to eliminate camera jerks.
    blend_factor: 0.0 = pure crop, 1.0 = pure wide fallback.
    """
    if not path_points:
        return 0.5, 0.5, 1.0, 1.0, "fallback", 1.0

    if t_ms <= path_points[0]['t_ms']:
        p = path_points[0]
        st = p.get('state', 'tracked')
        return p['cx'], p['cy'], p['w'], p['h'], st, (1.0 if st == 'fallback' else 0.0)
    if t_ms >= path_points[-1]['t_ms']:
        p = path_points[-1]
        st = p.get('state', 'tracked')
        return p['cx'], p['cy'], p['w'], p['h'], st, (1.0 if st == 'fallback' else 0.0)

    # Binary search for interval
    low = 0
    high = len(path_points) - 1
    while low <= high:
        mid = (low + high) // 2
        if path_points[mid]['t_ms'] <= t_ms:
            low = mid + 1
        else:
            high = mid - 1

    idx0 = max(0, high)
    idx1 = min(len(path_points) - 1, low)

    p0 = path_points[idx0]
    p1 = path_points[idx1]

    if idx0 == idx1 or p1['t_ms'] == p0['t_ms']:
        st = p0.get('state', 'tracked')
        return p0['cx'], p0['cy'], p0['w'], p0['h'], st, (1.0 if st == 'fallback' else 0.0)

    # Continuous interpolation with smoothstep ease-in/ease-out
    alpha = (t_ms - p0['t_ms']) / float(p1['t_ms'] - p0['t_ms'])
    smooth_alpha = alpha * alpha * (3.0 - 2.0 * alpha)

    cx = (1.0 - smooth_alpha) * p0['cx'] + smooth_alpha * p1['cx']
    cy = (1.0 - smooth_alpha) * p0['cy'] + smooth_alpha * p1['cy']
    w = (1.0 - smooth_alpha) * p0['w'] + smooth_alpha * p1['w']
    h = (1.0 - smooth_alpha) * p0['h'] + smooth_alpha * p1['h']

    # Blend factor calculation for seamless cross-dissolve
    p0_fb = (p0.get('state') == 'fallback')
    p1_fb = (p1.get('state') == 'fallback')

    if p0_fb and p1_fb:
        state = 'fallback'
        blend_factor = 1.0
    elif p0_fb and not p1_fb:
        state = 'interpolated'
        blend_factor = 1.0 - smooth_alpha
    elif not p0_fb and p1_fb:
        state = 'interpolated'
        blend_factor = smooth_alpha
    else:
        state = 'tracked'
        blend_factor = 0.0

    return cx, cy, w, h, state, blend_factor

class CpuMp4Renderer:
    def __init__(self, ffmpeg_exe: str = FFMPEG_EXE):
        self.ffmpeg_exe = ffmpeg_exe
        self.out_w = EXPORT_WIDTH
        self.out_h = EXPORT_HEIGHT

    def _render_letterbox(self, frame: np.ndarray, orig_w: int, orig_h: int) -> np.ndarray:
        bg_small = cv2.resize(frame, (180, 320))
        bg_blurred = cv2.GaussianBlur(bg_small, (25, 25), 0)
        out_frame = cv2.resize(bg_blurred, (self.out_w, self.out_h))
        out_frame = (out_frame * 0.60).astype(np.uint8)

        scale = min(self.out_w / float(orig_w), self.out_h / float(orig_h))
        scaled_w = int(orig_w * scale)
        scaled_h = int(orig_h * scale)
        scaled = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)

        y_off = (self.out_h - scaled_h) // 2
        x_off = (self.out_w - scaled_w) // 2
        out_frame[y_off:y_off + scaled_h, x_off:x_off + scaled_w] = scaled
        return out_frame

    def _render_crop(self, frame: np.ndarray, orig_w: int, orig_h: int, cx: float, cy: float, h: float) -> np.ndarray:
        target_h = int(round(h * orig_h))
        target_w = int(round(target_h * (9.0 / 16.0)))

        target_cx = int(round(cx * orig_w))
        target_cy = int(round(cy * orig_h))

        x1 = target_cx - target_w // 2
        y1 = target_cy - target_h // 2
        x2 = x1 + target_w
        y2 = y1 + target_h

        src_x1 = max(0, x1)
        src_y1 = max(0, y1)
        src_x2 = min(orig_w, x2)
        src_y2 = min(orig_h, y2)

        valid_crop = frame[src_y1:src_y2, src_x1:src_x2]

        if src_x1 == x1 and src_y1 == y1 and src_x2 == x2 and src_y2 == y2:
            return cv2.resize(valid_crop, (self.out_w, self.out_h), interpolation=cv2.INTER_LINEAR)
        else:
            # Out-of-bounds area is filled with pure black per user requirement, keeping subject dead-center
            canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)

            dst_x1 = src_x1 - x1
            dst_y1 = src_y1 - y1
            dst_x2 = dst_x1 + (src_x2 - src_x1)
            dst_y2 = dst_y1 + (src_y2 - src_y1)

            if valid_crop.size > 0:
                canvas[dst_y1:dst_y2, dst_x1:dst_x2] = valid_crop

            return cv2.resize(canvas, (self.out_w, self.out_h), interpolation=cv2.INTER_LINEAR)

    def render_person_fancam(
        self,
        source_path: str,
        person_id: str,
        camera_path: List[Dict[str, Any]],
        output_dir: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Renders an ultra-smooth, zero-distortion 9:16 person fancam MP4.
        Preserves perfect audio sync and creates ambient blur background for fallbacks and border margins.
        """
        os.makedirs(output_dir, exist_ok=True)
        final_mp4 = os.path.join(output_dir, f"{person_id}.mp4")
        temp_mp4 = os.path.join(output_dir, f"{person_id}_temp.mp4")

        if os.path.exists(final_mp4):
            return {'success': True, 'output_path': final_mp4, 'error': None}

        cap = cv2.VideoCapture(source_path)
        if not cap.isOpened():
            return {'success': False, 'output_path': '', 'error': f"Failed to open source {source_path}"}

        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-loglevel", "error",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{self.out_w}x{self.out_h}",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "-",                     # input 0: raw frames from stdin
            "-i", source_path,             # input 1: source file for audio
            "-map", "0:v:0",
            "-map", "1:a?",                # map audio from input 1 if available
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            "-f", "mp4",
            "-shortest",
            temp_mp4
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            cap.release()
            return {'success': False, 'output_path': '', 'error': f"Failed to start FFmpeg: {e}"}

        frame_idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                t_ms = int((frame_idx / fps) * 1000)
                cx, cy, w, h, state, blend_factor = interpolate_camera_roi(camera_path, t_ms)

                if blend_factor <= 0.005:
                    out_frame = self._render_crop(frame, orig_w, orig_h, cx, cy, h)
                elif blend_factor >= 0.995:
                    out_frame = self._render_letterbox(frame, orig_w, orig_h)
                else:
                    crop_f = self._render_crop(frame, orig_w, orig_h, cx, cy, h)
                    ltb_f = self._render_letterbox(frame, orig_w, orig_h)
                    out_frame = cv2.addWeighted(crop_f, 1.0 - blend_factor, ltb_f, blend_factor, 0.0)

                proc.stdin.write(out_frame.tobytes())
                frame_idx += 1

                if progress_callback and frame_idx % 30 == 0:
                    pct = (frame_idx / total_frames * 100) if total_frames > 0 else 0
                    progress_callback({
                        'person_id': person_id,
                        'frame_idx': frame_idx,
                        'total_frames': total_frames,
                        'percent': round(pct, 1)
                    })

            proc.stdin.close()
            proc.wait()

            if proc.returncode != 0:
                return {'success': False, 'output_path': '', 'error': f"FFmpeg failed with return code {proc.returncode}"}

            # Atomic replace: _temp.mp4 -> .mp4
            os.replace(temp_mp4, final_mp4)

            if progress_callback:
                progress_callback({
                    'person_id': person_id,
                    'frame_idx': frame_idx,
                    'total_frames': total_frames,
                    'percent': 100.0,
                    'finished': True
                })

            return {'success': True, 'output_path': os.path.abspath(final_mp4), 'error': None}

        except Exception as e:
            if proc.stdin:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
            proc.kill()
            return {'success': False, 'output_path': '', 'error': str(e)}
        finally:
            cap.release()
