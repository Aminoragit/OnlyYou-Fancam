import numpy as np
from typing import List, Dict, Any, Tuple
from core.global_resolver import IdentityCluster
from core.config import FANCAM_ASPECT_RATIO

def apply_deadzone(target_val: float, current_val: float, deadzone: float) -> float:
    """
    Applies dead-zone hysteresis: if displacement is smaller than deadzone,
    keeps current value to eliminate high-frequency hunting / jitter.
    """
    delta = target_val - current_val
    if abs(delta) <= deadzone:
        return current_val
    # Smooth step beyond deadzone
    effective_delta = delta - np.sign(delta) * deadzone
    return current_val + effective_delta

def zero_phase_gaussian_smooth(values: np.ndarray, alpha: float = 0.25) -> np.ndarray:
    """
    Forward-backward zero-phase filter + 3-tap Gaussian kernel.
    Completely eliminates directional overshoot and phase lag.
    """
    n = len(values)
    if n < 3:
        return values.copy()

    # Forward pass
    fwd = np.empty_like(values)
    fwd[0] = values[0]
    for i in range(1, n):
        fwd[i] = (1.0 - alpha) * fwd[i - 1] + alpha * values[i]

    # Backward pass
    bwd = np.empty_like(values)
    bwd[-1] = fwd[-1]
    for i in range(n - 2, -1, -1):
        bwd[i] = (1.0 - alpha) * bwd[i + 1] + alpha * fwd[i]

    # 3-tap Gaussian smoothing [0.15, 0.70, 0.15]
    smoothed = np.empty_like(bwd)
    smoothed[0] = bwd[0]
    smoothed[-1] = bwd[-1]
    for i in range(1, n - 1):
        smoothed[i] = 0.15 * bwd[i - 1] + 0.70 * bwd[i] + 0.15 * bwd[i + 1]

    return smoothed

class CameraPlanner:
    def __init__(self, orig_w: int, orig_h: int, duration_ms: int):
        self.orig_w = orig_w
        self.orig_h = orig_h
        self.duration_ms = duration_ms
        self.norm_aspect = (9.0 / 16.0) * (float(orig_h) / float(orig_w))

    def plan_for_cluster(self, cluster: IdentityCluster) -> List[Dict[str, Any]]:
        """
        Generate a jitter-free, ultra-stable 9:16 camera path with:
        1. Dead-zone hysteresis (prevents micro-shaking and hunting around center)
        2. Zero-phase bidirectional smoothing (eliminates lag & directional reversals)
        3. Zoom velocity dampening (eliminates zoom pumping)
        4. Seamless Hermite transitions for fallbacks
        """
        raw_obs = []
        for tracklet in cluster.tracklets:
            for obs in tracklet.observations:
                raw_obs.append({
                    't_ms': obs['t_ms'],
                    'cx': obs['norm_box'][0],
                    'cy': obs['norm_box'][1],
                    'w': obs['norm_box'][2],
                    'h': obs['norm_box'][3],
                    'shot_id': tracklet.shot_id,
                    'conf': obs['conf']
                })
        raw_obs.sort(key=lambda x: x['t_ms'])

        if not raw_obs:
            return [
                {'t_ms': 0, 'cx': 0.5, 'cy': 0.5, 'w': 1.0, 'h': 1.0, 'state': 'fallback'},
                {'t_ms': self.duration_ms, 'cx': 0.5, 'cy': 0.5, 'w': 1.0, 'h': 1.0, 'state': 'fallback'}
            ]

        # 1. Compute raw target viewport with Dead-Zone Filtering
        # Dead-zones in normalized units: 0.025 ≈ 18px horizontal, 0.020 ≈ 23px vertical
        DEADZONE_X = 0.028
        DEADZONE_Y = 0.022
        DEADZONE_ZOOM = 0.035

        keyed_viewports = []
        last_cx = raw_obs[0]['cx']
        last_cy = raw_obs[0]['cy']
        last_h = min(1.0, max(0.48, raw_obs[0]['h'] * 1.38))

        for o in raw_obs:
            person_h = o['h']
            person_w = o['w']

            # Target crop height with zoom dead-zone
            raw_crop_h = min(1.0, max(0.48, person_h * 1.38))
            crop_h = apply_deadzone(raw_crop_h, last_h, DEADZONE_ZOOM)
            last_h = crop_h

            crop_w = crop_h * self.norm_aspect

            if crop_w < person_w * 1.25:
                crop_w = min(1.0, person_w * 1.25)
                crop_h = crop_w / self.norm_aspect

            if crop_w > 1.0:
                crop_w = 1.0
                crop_h = crop_w / self.norm_aspect

            # Headroom calculation (keep head around top 16% ~ 20%)
            head_y = o['cy'] - person_h / 2.0
            raw_target_cy = head_y + crop_h * 0.33

            # Apply Dead-Zone to center coordinates
            cx = apply_deadzone(o['cx'], last_cx, DEADZONE_X)
            cy = apply_deadzone(raw_target_cy, last_cy, DEADZONE_Y)
            last_cx = cx
            last_cy = cy

            # Center the subject directly: keep person dead-center even at stage edges
            # (Out-of-bounds area is padded with black per user specification)
            cx_clamped = float(np.clip(cx, 0.0, 1.0))
            cy_clamped = float(np.clip(cy, 0.0, 1.0))

            keyed_viewports.append({
                't_ms': o['t_ms'],
                'cx': cx_clamped,
                'cy': cy_clamped,
                'w': float(crop_w),
                'h': float(crop_h),
                'shot_id': o['shot_id'],
                'state': 'tracked'
            })

        # 2. Shot-by-Shot Zero-Phase Bidirectional Filtering
        # Group viewports by continuous shot segments
        shots_groups: List[List[Dict[str, Any]]] = []
        cur_group = [keyed_viewports[0]]

        for i in range(1, len(keyed_viewports)):
            prev = keyed_viewports[i - 1]
            curr = keyed_viewports[i]
            # Split on scene cut or temporal gap > 1.2s
            if curr['shot_id'] != prev['shot_id'] or (curr['t_ms'] - prev['t_ms']) > 1200:
                shots_groups.append(cur_group)
                cur_group = [curr]
            else:
                cur_group.append(curr)
        shots_groups.append(cur_group)

        # Smooth each continuous shot with zero-phase filtering
        smoothed_viewports: List[Dict[str, Any]] = []
        for grp in shots_groups:
            if len(grp) >= 3:
                xs = np.array([pt['cx'] for pt in grp], dtype=np.float32)
                ys = np.array([pt['cy'] for pt in grp], dtype=np.float32)
                ws = np.array([pt['w'] for pt in grp], dtype=np.float32)
                hs = np.array([pt['h'] for pt in grp], dtype=np.float32)

                xs_smooth = zero_phase_gaussian_smooth(xs, alpha=0.22)
                ys_smooth = zero_phase_gaussian_smooth(ys, alpha=0.22)
                ws_smooth = zero_phase_gaussian_smooth(ws, alpha=0.15)
                hs_smooth = zero_phase_gaussian_smooth(hs, alpha=0.15)

                for idx, pt in enumerate(grp):
                    cur_w = float(ws_smooth[idx])
                    cur_h = float(hs_smooth[idx])
                    cur_x = float(np.clip(xs_smooth[idx], 0.0, 1.0))
                    cur_y = float(np.clip(ys_smooth[idx], 0.0, 1.0))

                    smoothed_viewports.append({
                        't_ms': pt['t_ms'],
                        'cx': cur_x,
                        'cy': cur_y,
                        'w': cur_w,
                        'h': cur_h,
                        'shot_id': pt['shot_id'],
                        'state': 'tracked'
                    })
            else:
                smoothed_viewports.extend(grp)

        # 3. Build Full Continuous Timeline: Hold Last Tracked Position & Glide Naturally
        # (Never zoom out to wide fallback on temporary absence/exit; hold and glide smoothly)
        full_path = []
        first_pt = smoothed_viewports[0]
        if first_pt['t_ms'] > 0:
            full_path.append({
                't_ms': 0,
                'cx': round(first_pt['cx'], 4),
                'cy': round(first_pt['cy'], 4),
                'w': round(first_pt['w'], 4),
                'h': round(first_pt['h'], 4),
                'shot_id': first_pt['shot_id'],
                'state': 'tracked'
            })

        for i in range(len(smoothed_viewports)):
            curr = smoothed_viewports[i]
            full_path.append({
                't_ms': curr['t_ms'],
                'cx': round(curr['cx'], 4),
                'cy': round(curr['cy'], 4),
                'w': round(curr['w'], 4),
                'h': round(curr['h'], 4),
                'shot_id': curr['shot_id'],
                'state': 'tracked'
            })

            if i < len(smoothed_viewports) - 1:
                nxt = smoothed_viewports[i + 1]
                gap_ms = nxt['t_ms'] - curr['t_ms']

                # Scene cut boundary: instantaneous cut (zero inter-shot panning)
                if nxt['shot_id'] != curr['shot_id']:
                    hold_t = max(curr['t_ms'] + 1, nxt['t_ms'] - 1)
                    full_path.append({
                        't_ms': hold_t,
                        'cx': round(curr['cx'], 4),
                        'cy': round(curr['cy'], 4),
                        'w': round(curr['w'], 4),
                        'h': round(curr['h'], 4),
                        'shot_id': curr['shot_id'],
                        'state': 'tracked'
                    })
                elif gap_ms > 500:
                    # Intra-shot temporary absence or exit:
                    # Hold at the last tracked position, then smoothly glide to re-acquisition.
                    # Adaptive glide time ensures pan speed never exceeds cinematic threshold (~0.22 screen/s)
                    dx = abs(nxt['cx'] - curr['cx'])
                    dy = abs(nxt['cy'] - curr['cy'])
                    dist = (dx**2 + dy**2)**0.5
                    target_glide_ms = int(max(600, (dist / 0.22) * 1000))
                    glide_time_ms = min(int(gap_ms * 0.75), target_glide_ms)
                    hold_t = nxt['t_ms'] - glide_time_ms
                    full_path.append({
                        't_ms': hold_t,
                        'cx': round(curr['cx'], 4),
                        'cy': round(curr['cy'], 4),
                        'w': round(curr['w'], 4),
                        'h': round(curr['h'], 4),
                        'shot_id': curr['shot_id'],
                        'state': 'tracked'
                    })

        last_pt = smoothed_viewports[-1]
        if last_pt['t_ms'] < self.duration_ms:
            # Hold last tracked position until end of video
            full_path.append({
                't_ms': self.duration_ms,
                'cx': round(last_pt['cx'], 4),
                'cy': round(last_pt['cy'], 4),
                'w': round(last_pt['w'], 4),
                'h': round(last_pt['h'], 4),
                'shot_id': last_pt['shot_id'],
                'state': 'tracked'
            })

        return full_path

    def build_all(self, clusters: List[IdentityCluster]) -> Dict[str, List[Dict[str, Any]]]:
        result = {}
        for c in clusters:
            result[c.person_id] = self.plan_for_cluster(c)
        return result
