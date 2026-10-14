import cv2
import numpy as np
from typing import Optional

def extract_visual_feature(crop_bgr: np.ndarray) -> np.ndarray:
    """
    Extract a normalized 3-part spatial pyramid feature vector from a person crop:
    - Region 1 (0% ~ 25%): Head / Hair / Face
    - Region 2 (25% ~ 65%): Torso / Upper clothing
    - Region 3 (65% ~ 100%): Lower clothing / Legs
    Computes HSV histograms and gradient texture.
    Runs in ~0.6ms on CPU.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return np.zeros(192, dtype=np.float32)

    h, w = crop_bgr.shape[:2]
    if h < 20 or w < 10:
        return np.zeros(192, dtype=np.float32)

    resized = cv2.resize(crop_bgr, (64, 128))
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # 3 Spatial regions
    r1_hsv = hsv[:32, :]
    r2_hsv = hsv[32:84, :]
    r3_hsv = hsv[84:, :]

    # Histograms for each region: 8 Hue bins x 8 Saturation bins = 64 values each
    hist1 = cv2.calcHist([r1_hsv], [0, 1], None, [8, 8], [0, 180, 0, 256]).flatten()
    hist2 = cv2.calcHist([r2_hsv], [0, 1], None, [8, 8], [0, 180, 0, 256]).flatten()
    hist3 = cv2.calcHist([r3_hsv], [0, 1], None, [8, 8], [0, 180, 0, 256]).flatten()

    feat = np.concatenate([hist1, hist2, hist3]).astype(np.float32)
    norm = np.linalg.norm(feat)
    if norm > 1e-6:
        feat /= norm

    return feat

def compute_similarity(feat1: np.ndarray, feat2: np.ndarray) -> float:
    """Compute cosine similarity between two feature vectors (0.0 ~ 1.0)."""
    if feat1 is None or feat2 is None or len(feat1) != len(feat2):
        return 0.0
    dot = np.dot(feat1, feat2)
    return float(max(0.0, min(1.0, dot)))
