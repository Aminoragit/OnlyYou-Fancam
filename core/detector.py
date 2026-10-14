import os
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
from core.config import YOLO_MODEL_PATH, DETECTOR_INPUT_SIZE, DETECTOR_CONF_THRESH, NMS_IOU_THRESH

def ensure_model_exists(model_path: str = YOLO_MODEL_PATH) -> bool:
    """Download ONNX model weights on demand if missing to maintain clean Apache-2.0 repository."""
    if os.path.exists(model_path) and os.path.getsize(model_path) > 1000000:
        return True
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    url = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx"
    print(f"[Detector] ONNX model weights not found. Downloading on-demand from public release...")
    try:
        import urllib.request
        urllib.request.urlretrieve(url, model_path)
        print(f"[Detector] Model downloaded successfully to {model_path}")
        return True
    except Exception as e:
        print(f"[Detector] Failed to auto-download model ({e}). Will use HOG detector fallback.")
        return False

class PersonDetector:
    def __init__(self, model_path: str = YOLO_MODEL_PATH, conf_thresh: float = DETECTOR_CONF_THRESH):
        self.conf_thresh = conf_thresh
        self.input_size = DETECTOR_INPUT_SIZE
        self.net = None
        self.use_hog_fallback = False

        # Ensure model is available on-demand
        ensure_model_exists(model_path)

        if os.path.exists(model_path):
            try:
                self.net = cv2.dnn.readNetFromONNX(model_path)
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                print(f"[Detector] Loaded YOLOv8n ONNX from {model_path}")
            except Exception as e:
                print(f"[Detector] Failed to load ONNX model: {e}. Falling back to HOG.")
                self.use_hog_fallback = True
        else:
            print("[Detector] ONNX model not found. Using HOG Person Detector.")
            self.use_hog_fallback = True

        if self.use_hog_fallback:
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect people in the given frame.
        Returns a list of dicts:
        [{
            'box': [x1, y1, x2, y2],          # pixel coords
            'conf': float,                    # confidence score (0.0 ~ 1.0)
            'norm_box': [cx, cy, w, h]        # normalized 0.0 ~ 1.0
        }, ...]
        """
        orig_h, orig_w = frame.shape[:2]
        if orig_h == 0 or orig_w == 0:
            return []

        if self.use_hog_fallback or self.net is None:
            return self._detect_hog(frame, orig_w, orig_h)

        try:
            return self._detect_yolov8(frame, orig_w, orig_h)
        except Exception as e:
            print(f"[Detector] YOLO forward error ({e}). Using HOG.")
            return self._detect_hog(frame, orig_w, orig_h)

    def _detect_yolov8(self, frame: np.ndarray, orig_w: int, orig_h: int) -> List[Dict[str, Any]]:
        inp_w, inp_h = self.input_size

        # Letterbox resize preserving aspect ratio with 114 gray padding (standard YOLO preprocessing)
        scale = min(inp_w / float(orig_w), inp_h / float(orig_h))
        new_w = int(round(orig_w * scale))
        new_h = int(round(orig_h * scale))
        pad_x = (inp_w - new_w) / 2.0
        pad_y = (inp_h - new_h) / 2.0

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        padded = np.full((inp_h, inp_w, 3), 114, dtype=np.uint8)
        ix = int(pad_x)
        iy = int(pad_y)
        padded[iy:iy + new_h, ix:ix + new_w] = resized

        blob = cv2.dnn.blobFromImage(padded, 1.0 / 255.0, (inp_w, inp_h), swapRB=True, crop=False)
        self.net.setInput(blob)
        preds = self.net.forward()  # Shape: (1, 84, 8400)

        if len(preds.shape) == 3:
            preds = preds[0].T  # (8400, 84)

        boxes = []
        confidences = []

        # Class 0 in COCO is person (column index 4)
        for row in preds:
            person_score = float(row[4])
            if person_score >= self.conf_thresh:
                cx_blob, cy_blob, w_blob, h_blob = row[0], row[1], row[2], row[3]
                # Invert letterbox transformations back to original frame space
                cx_orig = (cx_blob - pad_x) / scale
                cy_orig = (cy_blob - pad_y) / scale
                w_orig = w_blob / scale
                h_orig = h_blob / scale

                x1 = int(round(cx_orig - w_orig / 2.0))
                y1 = int(round(cy_orig - h_orig / 2.0))
                bw = int(round(w_orig))
                bh = int(round(h_orig))

                x1_clamped = max(0, x1)
                y1_clamped = max(0, y1)
                bw_clamped = min(orig_w - x1_clamped, bw)
                bh_clamped = min(orig_h - y1_clamped, bh)

                if bw_clamped > 12 and bh_clamped > 25:
                    boxes.append([x1_clamped, y1_clamped, bw_clamped, bh_clamped])
                    confidences.append(person_score)

        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_thresh, NMS_IOU_THRESH)
        results = []
        if len(indices) > 0:
            for idx in indices.flatten():
                bx, by, bw, bh = boxes[idx]
                x2 = min(orig_w, bx + bw)
                y2 = min(orig_h, by + bh)
                conf = confidences[idx]
                results.append({
                    'box': [bx, by, x2, y2],
                    'conf': round(conf, 3),
                    'norm_box': [
                        round((bx + x2) / (2.0 * orig_w), 4),
                        round((by + y2) / (2.0 * orig_h), 4),
                        round(bw / orig_w, 4),
                        round(bh / orig_h, 4)
                    ]
                })

        return results

    def _detect_hog(self, frame: np.ndarray, orig_w: int, orig_h: int) -> List[Dict[str, Any]]:
        small = cv2.resize(frame, (640, int(640 * orig_h / orig_w)))
        rects, weights = self.hog.detectMultiScale(small, winStride=(4, 4), padding=(8, 8), scale=1.05)
        scale_back = orig_w / 640.0

        results = []
        for (x, y, w, h), weight in zip(rects, weights):
            x1 = int(max(0, x * scale_back))
            y1 = int(max(0, y * scale_back))
            x2 = int(min(orig_w, (x + w) * scale_back))
            y2 = int(min(orig_h, (y + h) * scale_back))
            conf = float(min(1.0, max(0.4, weight[0] / 2.0)))
            results.append({
                'box': [x1, y1, x2, y2],
                'conf': round(conf, 3),
                'norm_box': [
                    round((x1 + x2) / (2.0 * orig_w), 4),
                    round((y1 + y2) / (2.0 * orig_h), 4),
                    round((x2 - x1) / orig_w, 4),
                    round((y2 - y1) / orig_h, 4)
                ]
            })
        return results
