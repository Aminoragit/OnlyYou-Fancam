import os
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Set, Optional
from core.tracker import Tracklet
from core.reid import compute_similarity

class IdentityCluster:
    def __init__(self, cluster_id: int):
        self.cluster_id = cluster_id
        self.person_id = f"person_{cluster_id:03d}"
        self.tracklets: List[Tracklet] = []
        self.best_crop: Optional[np.ndarray] = None
        self.best_conf: float = 0.0

    def add_tracklet(self, t: Tracklet):
        self.tracklets.append(t)
        if t.best_crop is not None and (t.best_conf > self.best_conf or self.best_crop is None):
            self.best_crop = t.best_crop
            self.best_conf = t.best_conf

    @property
    def total_observations(self) -> int:
        return sum(len(t.observations) for t in self.tracklets)

    @property
    def observed_frames(self) -> Set[int]:
        s = set()
        for t in self.tracklets:
            if hasattr(t, 'observed_frame_indices'):
                s.update(t.observed_frame_indices)
        return s

    @property
    def mean_feature(self) -> np.ndarray:
        feats = [t.mean_feature for t in self.tracklets if np.linalg.norm(t.mean_feature) > 0]
        if not feats:
            return np.zeros(128, dtype=np.float32)
        mf = np.mean(feats, axis=0)
        norm = np.linalg.norm(mf)
        if norm > 1e-6:
            mf /= norm
        return mf

def check_overlap(t1: Tracklet, t2: Tracklet) -> bool:
    """
    Check if two tracklets were observed in the exact same frame(s).
    Strict co-visibility constraint: two people visible at the same time CANNOT be the same person.
    """
    if hasattr(t1, 'observed_frame_indices') and hasattr(t2, 'observed_frame_indices'):
        return bool(t1.observed_frame_indices.intersection(t2.observed_frame_indices))
    return not (t1.end_t_ms < t2.start_t_ms or t2.end_t_ms < t1.start_t_ms)

class GlobalResolver:
    def __init__(self, sim_threshold: float = 0.48):
        self.sim_threshold = sim_threshold

    def resolve(
        self,
        tracklets: List[Tracklet],
        save_posters_dir: Optional[str] = None
    ) -> Tuple[List[IdentityCluster], int, float]:
        """
        Perform Constrained Clustering on tracklets.
        Enforces cannot-link constraint on simultaneous observations.
        Filters out transient noise tracklets.
        """
        if not tracklets:
            return [], 0, 0.0

        n = len(tracklets)

        # 1. Exact frame co-visibility mapping
        frame_occupancy: Dict[int, Set[int]] = {}
        for idx, t in enumerate(tracklets):
            frames = getattr(t, 'observed_frame_indices', set())
            for f in frames:
                frame_occupancy.setdefault(f, set()).add(idx)

        # Lower bound K_min is the true maximum simultaneous people seen in any single frame
        k_min = max((len(ts) for ts in frame_occupancy.values()), default=1)

        # 2. Build Cannot-Link matrix based on true co-visibility & kinematic velocity limits
        cannot_link = np.zeros((n, n), dtype=bool)
        for i in range(n):
            for j in range(i + 1, n):
                t1, t2 = tracklets[i], tracklets[j]
                if check_overlap(t1, t2):
                    cannot_link[i, j] = True
                    cannot_link[j, i] = True
                else:
                    # Kinematic velocity check: prevent merging tracklets of different performers
                    if t1.end_t_ms <= t2.start_t_ms:
                        gap_sec = (t2.start_t_ms - t1.end_t_ms) / 1000.0
                        dx = t2.observations[0]['norm_box'][0] - t1.observations[-1]['norm_box'][0]
                        dy = t2.observations[0]['norm_box'][1] - t1.observations[-1]['norm_box'][1]
                    else:
                        gap_sec = (t1.start_t_ms - t2.end_t_ms) / 1000.0
                        dx = t1.observations[0]['norm_box'][0] - t2.observations[-1]['norm_box'][0]
                        dy = t1.observations[0]['norm_box'][1] - t2.observations[-1]['norm_box'][1]

                    dist = (dx**2 + dy**2)**0.5
                    # Performer cannot teleport across stage (> 0.18 screen width in short gap, or > 0.32 screen/sec)
                    if (gap_sec < 1.5 and dist > 0.18) or (gap_sec > 0 and (dist / gap_sec) > 0.32):
                        cannot_link[i, j] = True
                        cannot_link[j, i] = True

        # 3. Compute pairwise visual appearance similarity
        sim_matrix = np.zeros((n, n), dtype=np.float32)
        for i in range(n):
            for j in range(i + 1, n):
                if not cannot_link[i, j]:
                    sim = compute_similarity(tracklets[i].mean_feature, tracklets[j].mean_feature)
                    sim_matrix[i, j] = sim
                    sim_matrix[j, i] = sim

        # 4. Constrained Hierarchical Clustering
        clusters: Dict[int, Set[int]] = {i: {i} for i in range(n)}

        while True:
            best_sim = -1.0
            merge_pair = None

            cluster_ids = list(clusters.keys())
            for idx_a in range(len(cluster_ids)):
                c_a = cluster_ids[idx_a]
                members_a = clusters[c_a]
                for idx_b in range(idx_a + 1, len(cluster_ids)):
                    c_b = cluster_ids[idx_b]
                    members_b = clusters[c_b]

                    # Verify no cannot-link violation between clusters
                    violates = False
                    for m_a in members_a:
                        for m_b in members_b:
                            if cannot_link[m_a, m_b]:
                                violates = True
                                break
                        if violates:
                            break

                    if violates:
                        continue

                    # Average similarity
                    sim_sum = sum(sim_matrix[m_a, m_b] for m_a in members_a for m_b in members_b)
                    avg_sim = sim_sum / (len(members_a) * len(members_b))

                    if avg_sim > best_sim:
                        best_sim = avg_sim
                        merge_pair = (c_a, c_b)

            # Stopping condition
            if merge_pair is None or best_sim < self.sim_threshold:
                break

            c_keep, c_remove = merge_pair
            clusters[c_keep].update(clusters[c_remove])
            del clusters[c_remove]

        # 5. Filter out noise / non-performer clusters
        # A valid performer should have meaningful sustained presence
        raw_clusters = []
        for members in clusters.values():
            total_obs = sum(len(tracklets[m].observations) for m in members)
            max_conf = max((tracklets[m].best_conf for m in members), default=0.0)
            all_h = [obs['norm_box'][3] for m in members for obs in tracklets[m].observations]
            mean_h = float(np.mean(all_h)) if all_h else 0.5
            raw_clusters.append({
                'members': members,
                'total_obs': total_obs,
                'max_conf': max_conf,
                'mean_h': mean_h,
                'score': total_obs * (1.0 + max_conf) * (mean_h ** 1.5)
            })

        # Sort by prominence (Main Ace Performers first)
        raw_clusters.sort(key=lambda x: x['score'], reverse=True)

        # Find maximum observations among candidate clusters
        max_cluster_obs = max((item['total_obs'] for item in raw_clusters), default=1)
        min_presence_obs = max(6, int(max_cluster_obs * 0.28))

        # Retain valid stage performers with substantial presence
        retained = []
        for idx, item in enumerate(raw_clusters):
            is_valid_size = (item['mean_h'] >= 0.20)
            is_core = (idx < k_min) and is_valid_size
            is_substantial = (item['total_obs'] >= min_presence_obs and item['mean_h'] >= 0.22 and item['max_conf'] >= 0.60)
            if is_core or is_substantial:
                retained.append(item)

        # Build final IdentityClusters
        final_clusters: List[IdentityCluster] = []
        for c_idx, item in enumerate(retained, start=1):
            cluster_obj = IdentityCluster(c_idx)
            for m in item['members']:
                cluster_obj.add_tracklet(tracklets[m])
            final_clusters.append(cluster_obj)

        k_estimated = len(final_clusters)
        k_confidence = 0.95 if k_estimated == k_min else 0.88

        # Save posters
        if save_posters_dir:
            os.makedirs(save_posters_dir, exist_ok=True)
            for c in final_clusters:
                poster_path = os.path.join(save_posters_dir, f"{c.person_id}.jpg")
                if c.best_crop is not None and c.best_crop.size > 0:
                    cv2.imwrite(poster_path, c.best_crop)
                else:
                    dummy = np.zeros((160, 90, 3), dtype=np.uint8)
                    cv2.imwrite(poster_path, dummy)

        return final_clusters, k_estimated, k_confidence
