"""
Smart Surveillance System - Vision Agent v3.0
Features:
  - Multi-camera support (pass camera indices as CLI args)
  - Pre-computed face encodings cache (.pkl)
  - DeepFace in background thread (non-blocking)
  - Facenet + cosine similarity whitelisting
  - API key authenticated FastAPI calls
Usage:
  python vision_agent.py            # single webcam (index 0)
  python vision_agent.py 0 1 2      # multi-camera (3 cameras)
"""

import os
import sys
import cv2
import time
import threading
import requests
import pickle
import numpy as np
from dotenv import load_dotenv
from ultralytics import YOLO
from deepface import DeepFace

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────
FASTAPI_URL      = "http://127.0.0.1:8000/v1/ingest-threat"
API_SECRET_KEY   = os.getenv("API_SECRET_KEY", "surv-secret-key-2026")
ALERT_IMAGE_PATH = "alert_frame.jpg"
FACE_MODEL       = "Facenet"
SIMILARITY_METRIC= "cosine"
VERIFY_THRESHOLD = 0.65  # Very lenient for easy recognition
COOLDOWN_SECONDS = 60   # 1 min gap — prevents Gemini free-tier rate limiting
YOLO_CONF        = 0.55
YOLO_INPUT_WIDTH = 640
ENCODINGS_FILE   = "face_encodings.pkl"
KNOWN_FACES_DIR  = "known_faces"

COLOR_AUTHORIZED   = (0, 210, 0)
COLOR_UNAUTHORIZED = (0, 0, 210)
COLOR_SCANNING     = (0, 200, 200)

# ─── Load Whitelist ────────────────────────────────────────────────────────────
def load_whitelist():
    """Load pre-computed encodings if available, else fall back to image paths."""
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, "rb") as f:
            db = pickle.load(f)
        total = sum(len(v) for v in db.values())
        print(f"[WHITELIST] Loaded cached encodings: {len(db)} person(s), {total} embeddings.")
        return db, "cached"

    whitelist = {}
    if os.path.exists(KNOWN_FACES_DIR):
        for person_name in os.listdir(KNOWN_FACES_DIR):
            p = os.path.join(KNOWN_FACES_DIR, person_name)
            if os.path.isdir(p):
                imgs = [os.path.join(p, f) for f in os.listdir(p)
                        if f.lower().endswith((".jpg", ".jpeg", ".png"))]
                if imgs:
                    whitelist[person_name] = imgs
                    print(f"[WHITELIST] Enrolled '{person_name}' ({len(imgs)} images)")
    print(f"[WHITELIST] {len(whitelist)} person(s) enrolled (live mode — run encode_faces.py for faster startup).")
    return whitelist, "live"

# ─── Face Verification ────────────────────────────────────────────────────────
def verify_face(crop, whitelist, mode):
    if mode == "cached":
        # Compare embedding directly
        try:
            result   = DeepFace.represent(img_path=crop, model_name=FACE_MODEL,
                                          enforce_detection=False)
            if not result:
                return False, "Unknown"
            probe_emb = np.array(result[0]["embedding"])
            best_dist = 1.0
            best_name = "Unknown"
            for person_name, embeddings in whitelist.items():
                for emb in embeddings:
                    gallery_emb = np.array(emb)
                    # Cosine distance
                    dot  = np.dot(probe_emb, gallery_emb)
                    norm = np.linalg.norm(probe_emb) * np.linalg.norm(gallery_emb)
                    dist = 1 - (dot / norm) if norm else 1.0
                    if dist < best_dist:
                        best_dist = dist
                        best_name = person_name
            return (best_dist < VERIFY_THRESHOLD, best_name if best_dist < VERIFY_THRESHOLD else "Unknown")
        except Exception:
            return False, "Unknown"
    else:
        # Live mode: use DeepFace.verify against image files
        for person_name, image_paths in whitelist.items():
            for img_path in image_paths:
                try:
                    res = DeepFace.verify(img1_path=crop, img2_path=img_path,
                                          model_name=FACE_MODEL,
                                          distance_metric=SIMILARITY_METRIC,
                                          enforce_detection=False)
                    if res.get("verified") or res.get("distance", 1.0) < VERIFY_THRESHOLD:
                        return True, person_name
                except Exception:
                    continue
        return False, "Unknown"

# ─── API Trigger (fire-and-forget) ────────────────────────────────────────────
def trigger_backend_api(image_path, status="unknown_threat"):
    """Send alert image and status to FastAPI bridge."""
    def _send():
        try:
            with open(image_path, "rb") as f:
                files   = {"file": (os.path.basename(image_path), f, "image/jpeg")}
                headers = {"X-API-Key": API_SECRET_KEY}
                params  = {"status": status}
                response = requests.post(FASTAPI_URL, files=files, headers=headers, params=params)
                print(f"[API] Frame sent. Status: {response.status_code}")
        except Exception as e:
            print(f"[API] Error triggering bridge: {e}")
    threading.Thread(target=_send, daemon=True).start()

# ─── Draw Overlay ─────────────────────────────────────────────────────────────
def draw_label(frame, box, label, color):
    x1, y1, x2, y2 = box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    sz, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
    cv2.rectangle(frame, (x1, y1 - sz[1] - 10), (x1 + sz[0] + 6, y1), color, cv2.FILLED)
    cv2.putText(frame, label, (x1 + 3, y1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

# ─── Background Face Recognizer ───────────────────────────────────────────────
class FaceRecognizer:
    def __init__(self, whitelist, mode):
        self.whitelist   = whitelist
        self.mode        = mode
        self.lock        = threading.Lock()
        self._busy       = False
        self.result      = None
        self._last_alert = 0.0

    def is_busy(self):
        with self.lock:
            return self._busy

    def submit(self, crop, box, full_frame):
        with self.lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._run,
                         args=(crop.copy(), box, full_frame.copy()), daemon=True).start()

    def _run(self, crop, box, full_frame):
        try:
            authorized, name = verify_face(crop, self.whitelist, self.mode)
            if authorized:
                label, color = f"Authorized - {name.capitalize()}", COLOR_AUTHORIZED
                print(f"[CAM] Authorized: {name.capitalize()}")
                # Log authorized detection to dashboard too
                now = time.time()
                if now - self._last_alert > COOLDOWN_SECONDS:
                    cv2.imwrite(ALERT_IMAGE_PATH, full_frame)
                    trigger_backend_api(ALERT_IMAGE_PATH, status="authorized")
                    self._last_alert = now
            else:
                label, color = "Unauthorized - Unknown", COLOR_UNAUTHORIZED
                print("[CAM] ALERT: Unknown person!")
                now = time.time()
                if now - self._last_alert > COOLDOWN_SECONDS:
                    cv2.imwrite(ALERT_IMAGE_PATH, full_frame)
                    trigger_backend_api(ALERT_IMAGE_PATH, status="unknown_threat")
                    self._last_alert = now
            with self.lock:
                self.result = (box, label, color)
        finally:
            with self.lock:
                self._busy = False

# ─── Per-Camera Thread ────────────────────────────────────────────────────────
def run_camera(cam_index: int, model: YOLO, whitelist: dict, mode: str):
    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        print(f"[CAM-{cam_index}] ERROR: Cannot open camera.")
        return
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    recognizer = FaceRecognizer(whitelist, mode)
    fps_timer  = time.time()
    fps        = 0.0
    frame_cnt  = 0
    h_orig = w_orig = None
    win_name = f"Surveillance — Camera {cam_index}"

    print(f"[CAM-{cam_index}] Started. Press 'q' on this window to stop.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_cnt += 1
        if h_orig is None:
            h_orig, w_orig = frame.shape[:2]

        elapsed = time.time() - fps_timer
        if elapsed >= 0.5:
            fps = frame_cnt / elapsed
            frame_cnt = 0
            fps_timer = time.time()

        # YOLO on downscaled frame
        scale = YOLO_INPUT_WIDTH / w_orig
        small = cv2.resize(frame, (YOLO_INPUT_WIDTH, int(h_orig * scale)))
        inv   = 1.0 / scale

        results      = model(small, stream=True, verbose=False, classes=[0], conf=YOLO_CONF)
        person_boxes = []
        for r in results:
            for box in r.boxes:
                sx1, sy1, sx2, sy2 = map(int, box.xyxy[0])
                person_boxes.append((
                    max(0, int(sx1 * inv)), max(0, int(sy1 * inv)),
                    min(w_orig, int(sx2 * inv)), min(h_orig, int(sy2 * inv))
                ))

        # Submit to background thread when idle
        if person_boxes and not recognizer.is_busy():
            x1, y1, x2, y2 = person_boxes[0]
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                recognizer.submit(crop, person_boxes[0], frame)

        # Draw
        if recognizer.result:
            draw_label(frame, *recognizer.result[:3])
            for b in person_boxes[1:]:
                draw_label(frame, b, "Scanning...", COLOR_SCANNING)
        elif person_boxes:
            for b in person_boxes:
                draw_label(frame, b, "Scanning...", COLOR_SCANNING)

        h, w = frame.shape[:2]
        cv2.putText(frame, f"CAM {cam_index}  FPS: {fps:.1f}  Persons: {len(person_boxes)}",
                    (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        cv2.imshow(win_name, frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    try:
        cv2.destroyWindow(win_name)
    except Exception:
        pass
    print(f"[CAM-{cam_index}] Stopped.")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("   Smart Surveillance Engine v3.0 — Multi-Camera")
    print("=" * 60)

    # Camera indices from CLI args, default to [0]
    cam_indices = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [0]
    print(f"[INIT] Cameras to use: {cam_indices}")

    whitelist, mode = load_whitelist()

    print("[INIT] Loading YOLOv8n...")
    model = YOLO("yolov8n.pt")
    print("[INIT] YOLOv8n ready.\n")

    if len(cam_indices) == 1:
        # Single camera — run in main thread
        run_camera(cam_indices[0], model, whitelist, mode)
    else:
        # Multi-camera — each in its own thread
        threads = []
        for idx in cam_indices:
            t = threading.Thread(target=run_camera,
                                 args=(idx, model, whitelist, mode), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

    print("[EXIT] All cameras stopped.")

if __name__ == "__main__":
    main()
