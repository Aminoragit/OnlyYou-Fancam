import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from core.reid import extract_visual_feature

def compute_iou(boxA, boxB) -> float:
    # box: [x1, y1, x2, y2]
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = max(1, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(1, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    iou = interArea / float(boxAArea + boxBArea - interArea)
    return max(0.0, min(1.0, iou))

class ShotDetector:
    def __init__(self, diff_threshold: float = 35.0):
        self.diff_threshold = diff_threshold
        self.prev_small_gray = None
        self.current_shot_id = 0

    def check_shot_cut(self, frame_bgr: np.ndarray) -> Tuple[bool, int]:
        """
        Check if the current frame represents a scene cut.
        Returns: (is_cut, shot_id)
        """
        small_gray = cv2.resize(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY), (160, 90))
        if self.prev_small_gray is None:
            self.prev_small_gray = small_gray
            return False, self.current_shot_id

        diff = np.mean(cv2.absdiff(small_gray, self.prev_small_gray))
        self.prev_small_gray = small_gray

        if diff > self.diff_threshold:
            self.current_shot_id += 1
            return True, self.current_shot_id

        return False, self.current_shot_id

class Tracklet:
    def __init__(self, tracklet_id: int, shot_id: int, initial_obs: Dict[str, Any], crop_bgr: Optional[np.ndarray]):
        self.tracklet_id = tracklet_id
        self.shot_id = shot_id
        self.observations = [initial_obs]
        self.observed_frame_indices = {initial_obs['frame_idx']}
        self.lost_frames = 0
        self.features = []
        if crop_bgr is not None and crop_bgr.size > 0:
            feat = extract_visual_feature(crop_bgr)
            self.features.append(feat)
            self.best_crop = crop_bgr.copy()
            self.best_conf = initial_obs['conf']
        else:
            self.best_crop = None
            self.best_conf = 0.0

    def add_observation(self, obs: Dict[str, Any], crop_bgr: Optional[np.ndarray]):
        self.observations.append(obs)
        self.observed_frame_indices.add(obs['frame_idx'])
        if crop_bgr is not None and crop_bgr.size > 0:
            # Sample features periodically to save CPU
            if len(self.features) < 8 or len(self.observations) % 2 == 0:
                feat = extract_visual_feature(crop_bgr)
                self.features.append(feat)
            if obs['conf'] > self.best_conf or self.best_crop is None:
                self.best_crop = crop_bgr.copy()
                self.best_conf = obs['conf']

    @property
    def mean_feature(self) -> np.ndarray:
        if not self.features:
            return np.zeros(128, dtype=np.float32)
        mean_f = np.mean(self.features, axis=0)
        norm = np.linalg.norm(mean_f)
        if norm > 1e-6:
            mean_f /= norm
        return mean_f

    @property
    def start_t_ms(self) -> int:
        return self.observations[0]['t_ms']

    @property
    def end_t_ms(self) -> int:
        return self.observations[-1]['t_ms']

    @property
    def last_box(self) -> List[int]:
        return self.observations[-1]['box']

class ShotTracker:
    def __init__(self, iou_thresh: float = 0.30, max_lost_frames: int = 4):
        self.iou_thresh = iou_thresh
        self.max_lost_frames = max_lost_frames
        self.tracklet_counter = 0
        self.active_tracklets: List[Tracklet] = []
        self.completed_tracklets: List[Tracklet] = []
        self.last_shot_id = -1

    def update(
        self,
        shot_id: int,
        is_cut: bool,
        frame_idx: int,
        t_ms: int,
        detections: List[Dict[str, Any]],
        frame_bgr: np.ndarray
    ):
        """
        Update tracking for the current frame.
        """
        # If scene cut occurred, complete all active tracklets immediately
        if is_cut or shot_id != self.last_shot_id:
            self.completed_tracklets.extend(self.active_tracklets)
            self.active_tracklets = []
            self.last_shot_id = shot_id

        orig_h, orig_w = frame_bgr.shape[:2]

        # Match active tracklets with detections via sorted Maximum Weight Matching
        matches = []
        unmatched_tracks = list(range(len(self.active_tracklets)))
        unmatched_dets = list(range(len(detections)))

        if self.active_tracklets and detections:
            candidates = []
            for t_idx, tracklet in enumerate(self.active_tracklets):
                last_box = tracklet.last_box
                for d_idx, det in enumerate(detections):
                    iou = compute_iou(last_box, det['box'])
                    if iou >= self.iou_thresh:
                        candidates.append((iou, t_idx, d_idx))

            # Highest IoU match takes priority
            candidates.sort(key=lambda x: x[0], reverse=True)

            matched_tracks = set()
            matched_dets = set()
            for iou, t_idx, d_idx in candidates:
                if t_idx not in matched_tracks and d_idx not in matched_dets:
                    matches.append((t_idx, d_idx))
                    matched_tracks.add(t_idx)
                    matched_dets.add(d_idx)

            unmatched_tracks = [t for t in range(len(self.active_tracklets)) if t not in matched_tracks]
            unmatched_dets = [d for d in range(len(detections)) if d not in matched_dets]

        # Update matched tracklets
        for t_idx, d_idx in matches:
            det = detections[d_idx]
            bx = det['box']
            crop = frame_bgr[max(0, bx[1]):min(orig_h, bx[3]), max(0, bx[0]):min(orig_w, bx[2])]
            obs = {
                't_ms': t_ms,
                'frame_idx': frame_idx,
                'box': bx,
                'norm_box': det['norm_box'],
                'conf': det['conf']
            }
            self.active_tracklets[t_idx].add_observation(obs, crop)
            self.active_tracklets[t_idx].lost_frames = 0

        # Unmatched active tracks: tolerate up to max_lost_frames before finalizing
        still_active = []
        for t_idx in range(len(self.active_tracklets)):
            if t_idx in unmatched_tracks:
                self.active_tracklets[t_idx].lost_frames += 1
                if self.active_tracklets[t_idx].lost_frames > self.max_lost_frames:
                    # Finalize after exceeding allowed lost duration
                    self.completed_tracklets.append(self.active_tracklets[t_idx])
                else:
                    still_active.append(self.active_tracklets[t_idx])
            else:
                still_active.append(self.active_tracklets[t_idx])
        self.active_tracklets = still_active

        # Create new tracklets for unmatched detections
        for d_idx in unmatched_dets:
            det = detections[d_idx]
            bx = det['box']
            crop = frame_bgr[max(0, bx[1]):min(orig_h, bx[3]), max(0, bx[0]):min(orig_w, bx[2])]
            obs = {
                't_ms': t_ms,
                'frame_idx': frame_idx,
                'box': bx,
                'norm_box': det['norm_box'],
                'conf': det['conf']
            }
            self.tracklet_counter += 1
            new_track = Tracklet(self.tracklet_counter, shot_id, obs, crop)
            self.active_tracklets.append(new_track)

    def finalize(self) -> List[Tracklet]:
        """Finalize and return all valid tracklets."""
        self.completed_tracklets.extend(self.active_tracklets)
        self.active_tracklets = []
        # Filter out extremely short tracklets (noise/glitches)
        valid_tracklets = [t for t in self.completed_tracklets if len(t.observations) >= 2 or t.best_conf >= 0.5]
        return valid_tracklets
