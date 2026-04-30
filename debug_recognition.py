"""
debug_recognition.py — Diagnose face recognition issue
Run: python debug_recognition.py
"""
import os, pickle, cv2
import numpy as np
from deepface import DeepFace

ENCODINGS_FILE = "face_encodings.pkl"
FACE_MODEL     = "Facenet"

print("=" * 60)
print("  Face Recognition Diagnostic")
print("=" * 60)

# Step 1 — Check cache
if not os.path.exists(ENCODINGS_FILE):
    print("[ERROR] face_encodings.pkl NOT FOUND. Run encode_faces.py first.")
    exit()

with open(ENCODINGS_FILE, "rb") as f:
    db = pickle.load(f)

print(f"\n[OK] Cache loaded: {len(db)} person(s)")
for name, embs in db.items():
    print(f"  - {name}: {len(embs)} embeddings")

# Step 2 — Capture a live frame
print("\n[CAMERA] Opening webcam to capture test frame...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Cannot open webcam.")
    exit()

print("[CAMERA] Look at the camera. Press SPACE to capture, Q to quit.")
frame = None
while True:
    ret, f = cap.read()
    if not ret:
        break
    cv2.putText(f, "Press SPACE to capture | Q to quit", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow("Capture Test Frame", f)
    key = cv2.waitKey(1) & 0xFF
    if key == ord(' '):
        frame = f.copy()
        break
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

if frame is None:
    print("[ERROR] No frame captured.")
    exit()

cv2.imwrite("debug_frame.jpg", frame)
print("[OK] Frame saved: debug_frame.jpg")

# Step 3 — Get embedding for live frame
print("\n[DEEPFACE] Computing embedding for live frame...")
try:
    result = DeepFace.represent(
        img_path=frame,
        model_name=FACE_MODEL,
        enforce_detection=False
    )
    if not result:
        print("[ERROR] No face detected in live frame!")
        exit()
    
    probe_emb = np.array(result[0]["embedding"])
    print(f"[OK] Live embedding computed. Size: {len(probe_emb)}")
except Exception as e:
    print(f"[ERROR] DeepFace.represent failed: {e}")
    exit()

# Step 4 — Compute cosine distances to all cached embeddings
print("\n[MATCHING] Cosine distances to all cached embeddings:")
print("-" * 40)

best_dist  = 1.0
best_name  = "Unknown"

for person_name, embeddings in db.items():
    person_min = 1.0
    for i, emb in enumerate(embeddings):
        gallery_emb = np.array(emb)
        dot  = np.dot(probe_emb, gallery_emb)
        norm = np.linalg.norm(probe_emb) * np.linalg.norm(gallery_emb)
        dist = 1 - (dot / norm) if norm else 1.0
        print(f"  {person_name} img[{i}] -> distance: {dist:.4f}")
        if dist < person_min:
            person_min = dist
        if dist < best_dist:
            best_dist = dist
            best_name = person_name
    print(f"  >> Best for {person_name}: {person_min:.4f}")

print("\n" + "=" * 40)
print(f"RESULT: Best match = '{best_name}' | Distance = {best_dist:.4f}")
print(f"  Threshold 0.65 -> {'AUTHORIZED' if best_dist < 0.65 else 'REJECTED'}")
print(f"  Threshold 0.50 -> {'AUTHORIZED' if best_dist < 0.50 else 'REJECTED'}")
print(f"  Threshold 0.40 -> {'AUTHORIZED' if best_dist < 0.40 else 'REJECTED'}")
print("=" * 40)

if best_dist >= 0.65:
    print("\n[DIAGNOSIS] Your face is not matching. Possible reasons:")
    print("  1. The cached embeddings were computed from WhatsApp images (compressed).")
    print("  2. Camera quality / lighting is very different from training images.")
    print("  3. Try taking new photos via webcam and adding to known_faces/shiivu/")
