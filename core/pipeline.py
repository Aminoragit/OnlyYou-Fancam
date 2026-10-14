import os
import time
import json
import threading
import cv2
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from core.config import JOBS_DIR, DEFAULT_SCAN_FPS
from core.media_probe import probe_video
from core.detector import PersonDetector
from core.tracker import ShotDetector, ShotTracker
from core.global_resolver import GlobalResolver
from core.camera_planner import CameraPlanner
from core.renderer import CpuMp4Renderer

class FancamJob:
    def __init__(self, source_path: str, job_id: Optional[str] = None):
        self.job_id = job_id or f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.source_path = os.path.abspath(source_path)
        self.job_dir = os.path.join(JOBS_DIR, self.job_id)
        self.preview_dir = os.path.join(self.job_dir, "preview")
        self.export_dir = os.path.join(self.job_dir, "export")
        os.makedirs(self.preview_dir, exist_ok=True)
        os.makedirs(self.export_dir, exist_ok=True)

        self.source_info: Dict[str, Any] = {}
        self.preview_state: str = "NOT_STARTED"
        self.export_state: str = "WAITING"
        self.progress_msg: str = "Initialized"
        self.fast_lane_percent: float = 0.0
        self.export_percent: float = 0.0

        self.k_initial: int = 0
        self.k_confidence: float = 0.0
        self.identities: List[Dict[str, Any]] = []
        self.camera_paths: Dict[str, List[Dict[str, Any]]] = {}
        self.export_files: List[Dict[str, Any]] = []

        self.timing: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]):
        with self._lock:
            self._listeners.append(callback)

    def emit_update(self):
        snapshot = self.to_dict()
        with self._lock:
            for cb in self._listeners:
                try:
                    cb(snapshot)
                except Exception:
                    pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'source_path': self.source_path,
            'source_info': self.source_info,
            'preview_state': self.preview_state,
            'export_state': self.export_state,
            'progress_msg': self.progress_msg,
            'fast_lane_percent': self.fast_lane_percent,
            'export_percent': self.export_percent,
            'k_initial': self.k_initial,
            'k_confidence': self.k_confidence,
            'identities': self.identities,
            'export_files': self.export_files,
            'timing': self.timing,
            'error': self.error
        }

    def save_manifest(self):
        manifest_path = os.path.join(self.preview_dir, "preview_manifest_v1.json")
        temp_path = os.path.join(self.preview_dir, "preview_manifest_v1.json.tmp")
        data = self.to_dict()
        data['camera_paths'] = self.camera_paths
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, manifest_path)

    def generate_qa_report(self) -> Dict[str, Any]:
        qa_dir = os.path.join(self.job_dir, "qa")
        os.makedirs(qa_dir, exist_ok=True)
        report_path = os.path.join(qa_dir, "qa_report.json")

        performer_metrics = {}
        any_warnings = []

        for pid, path in self.camera_paths.items():
            if not path:
                performer_metrics[pid] = {'status': 'EMPTY'}
                continue
            n_pts = len(path)
            fb_pts = sum(1 for p in path if p.get('state') == 'fallback')
            fb_pct = round((fb_pts / n_pts) * 100.0, 1)

            xs = [p['cx'] for p in path]
            ys = [p['cy'] for p in path]
            ws = [p['w'] for p in path]
            hs = [p['h'] for p in path]

            min_x = min(xs[i] - ws[i] / 2.0 for i in range(n_pts))
            max_x = max(xs[i] + ws[i] / 2.0 for i in range(n_pts))
            min_y = min(ys[i] - hs[i] / 2.0 for i in range(n_pts))
            max_y = max(ys[i] + hs[i] / 2.0 for i in range(n_pts))

            warnings = []
            if fb_pct > 50.0:
                warnings.append("EXCESSIVE_FALLBACK")

            black_padding_needed = (min_x < -0.01 or max_x > 1.01 or min_y < -0.01 or max_y > 1.01)

            if warnings:
                any_warnings.extend([f"{pid}: {w}" for w in warnings])

            performer_metrics[pid] = {
                'total_keyframes': n_pts,
                'fallback_percent': fb_pct,
                'black_padding_applied': black_padding_needed,
                'viewport_bounds': {
                    'min_x': round(min_x, 4),
                    'max_x': round(max_x, 4),
                    'min_y': round(min_y, 4),
                    'max_y': round(max_y, 4)
                },
                'warnings': warnings
            }

        # Exported files QA
        export_qa = []
        for exp in self.export_files:
            fpath = exp.get('file_path')
            if fpath and os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    header = f.read(1024)
                    faststart = b"moov" in header
                export_qa.append({
                    'person_id': exp.get('person_id'),
                    'file_size_bytes': os.path.getsize(fpath),
                    'faststart_ready': faststart
                })

        report = {
            'job_id': self.job_id,
            'timestamp': datetime.now().isoformat(),
            'source_path': self.source_path,
            'k_estimated': self.k_initial,
            'k_confidence': self.k_confidence,
            'overall_status': 'WARNING' if any_warnings else 'PASS',
            'warnings': any_warnings,
            'performer_metrics': performer_metrics,
            'export_metrics': export_qa
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

class FancamPipeline:
    def __init__(self):
        self.detector = PersonDetector()
        self.renderer = CpuMp4Renderer()

    def run_job_async(self, job: FancamJob):
        """Run the 3-lane pipeline in a background worker thread."""
        t = threading.Thread(target=self._run_pipeline, args=(job,), daemon=True)
        t.start()
        return t

    def _run_pipeline(self, job: FancamJob):
        t0 = time.time()
        try:
            # 1. Media Probe
            job.progress_msg = "Probing video format and streams..."
            job.preview_state = "PROBING"
            job.emit_update()

            source_info = probe_video(job.source_path)
            job.source_info = source_info
            orig_w = source_info['width']
            orig_h = source_info['height']
            duration_ms = source_info['duration_ms']
            total_frames = source_info['total_frames']
            fps = source_info['fps']

            if total_frames <= 0 or duration_ms <= 0:
                raise ValueError("Video has 0 frames or invalid duration.")

            # 2. Fast Lane: Sequential Scan with Adaptive Sampling
            job.preview_state = "SCANNING"
            job.progress_msg = "Fast Lane: Scanning video, detecting performers and shots..."
            job.emit_update()

            shot_detector = ShotDetector()
            tracker = ShotTracker(iou_thresh=0.35)

            cap = cv2.VideoCapture(job.source_path)
            sample_step = max(1, int(round(fps / DEFAULT_SCAN_FPS)))

            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_step == 0:
                    t_ms = int((frame_idx / fps) * 1000)
                    is_cut, shot_id = shot_detector.check_shot_cut(frame)
                    dets = self.detector.detect(frame)
                    tracker.update(shot_id, is_cut, frame_idx, t_ms, dets, frame)

                    pct = min(90.0, (frame_idx / total_frames) * 90.0)
                    job.fast_lane_percent = round(pct, 1)
                    if frame_idx % (sample_step * 10) == 0:
                        job.progress_msg = f"Fast Lane: Scanned {frame_idx}/{total_frames} frames ({job.fast_lane_percent}%)..."
                        job.emit_update()

                frame_idx += 1

            cap.release()

            # 3. Finalize Tracklets & Global Resolution (Cannot-Link Constrained Clustering)
            job.progress_msg = "Fast Lane: Resolving global identities and estimating performer count K..."
            job.fast_lane_percent = 92.0
            job.emit_update()

            tracklets = tracker.finalize()
            posters_dir = os.path.join(job.preview_dir, "posters")
            resolver = GlobalResolver(sim_threshold=0.50)
            clusters, k_est, k_conf = resolver.resolve(tracklets, save_posters_dir=posters_dir)

            job.k_initial = k_est
            job.k_confidence = k_conf

            # 4. Camera Path Generation (9:16 Smooth Crop + Wide Fallback)
            job.preview_state = "CAMERA_PATH_BUILDING"
            job.progress_msg = f"Generating 9:16 virtual fancam paths for {k_est} identified performers..."
            job.fast_lane_percent = 96.0
            job.emit_update()

            planner = CameraPlanner(orig_w, orig_h, duration_ms)
            camera_paths = planner.build_all(clusters)
            job.camera_paths = camera_paths

            # Build identities list for UI
            identities = []
            for c in clusters:
                total_obs = c.total_observations
                duration_tracked_sec = round((total_obs * sample_step) / fps, 1)
                identities.append({
                    'person_id': c.person_id,
                    'confidence': round(c.best_conf, 2),
                    'total_tracked_sec': duration_tracked_sec,
                    'poster_url': f"/api/jobs/{job.job_id}/posters/{c.person_id}.jpg"
                })
            job.identities = identities

            # 5. Fast Lane Complete -> PREVIEW_READY!
            t_fast_lane = time.time() - t0
            job.timing['fast_lane_sec'] = round(t_fast_lane, 2)
            job.fast_lane_percent = 100.0
            job.preview_state = "PREVIEW_READY"
            job.progress_msg = f"Virtual Fancams Ready for {k_est} performers ({job.timing['fast_lane_sec']}s)! Ready to play."
            job.save_manifest()
            job.emit_update()

            # 6. Export Lane: Auto-render K MP4s in background without requiring user clicks
            job.export_state = "ENCODING"
            job.progress_msg = f"Export Lane: Automatically rendering {k_est} individual 9:16 MP4 fancams in background..."
            job.emit_update()

            export_files = []
            total_k = len(clusters)
            for k_idx, c in enumerate(clusters, start=1):
                pid = c.person_id
                c_path = camera_paths.get(pid, [])
                job.progress_msg = f"Export Lane: Rendering {pid} ({k_idx}/{total_k})..."
                job.emit_update()

                def _render_cb(d):
                    # Combine overall export progress
                    per_file_pct = d.get('percent', 0.0)
                    overall = ((k_idx - 1) + (per_file_pct / 100.0)) / total_k * 100.0
                    job.export_percent = round(overall, 1)
                    job.emit_update()

                render_res = self.renderer.render_person_fancam(
                    source_path=job.source_path,
                    person_id=pid,
                    camera_path=c_path,
                    output_dir=job.export_dir,
                    progress_callback=_render_cb
                )

                if render_res['success']:
                    export_files.append({
                        'person_id': pid,
                        'file_path': render_res['output_path'],
                        'download_url': f"/api/jobs/{job.job_id}/exports/{pid}.mp4",
                        'state': 'completed'
                    })
                else:
                    export_files.append({
                        'person_id': pid,
                        'file_path': '',
                        'download_url': '',
                        'state': 'failed',
                        'error': render_res.get('error')
                    })
                job.export_files = export_files
                job.save_manifest()
                job.emit_update()

            job.export_percent = 100.0
            job.export_state = "ALL_EXPORTED"
            job.timing['total_sec'] = round(time.time() - t0, 2)
            job.save_manifest()
            try:
                job.generate_qa_report()
            except Exception as qa_err:
                print(f"[QA Report Error] {qa_err}")
            job.emit_update()

        except Exception as e:
            import traceback
            traceback.print_exc()
            job.error = str(e)
            job.preview_state = "FAILED"
            job.export_state = "FAILED"
            job.progress_msg = f"Error: {e}"
            job.emit_update()
