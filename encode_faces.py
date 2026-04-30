"""
encode_faces.py — Face Encoding Pre-computation
Run this ONCE to pre-compute and cache face embeddings for all known persons.
Subsequent runs of vision_agent.py will be faster as a result.
Usage: python encode_faces.py
"""
import os
import pickle
from deepface import DeepFace

KNOWN_FACES_DIR = "known_faces"
ENCODINGS_FILE  = "face_encodings.pkl"
FACE_MODEL      = "Facenet"

print("=" * 50)
print("  Face Encoding Pre-computation")
print("=" * 50)

encodings_db = {}  # { person_name: [embedding_vector, ...] }

for person_name in os.listdir(KNOWN_FACES_DIR):
    person_path = os.path.join(KNOWN_FACES_DIR, person_name)
    if not os.path.isdir(person_path):
        continue

    images = [
        os.path.join(person_path, f)
        for f in os.listdir(person_path)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    if not images:
        continue

    print(f"\n[{person_name}] Processing {len(images)} image(s)...")
    embeddings = []
    for img_path in images:
        try:
            result = DeepFace.represent(
                img_path=img_path,
                model_name=FACE_MODEL,
                enforce_detection=False
            )
            if result:
                embeddings.append(result[0]["embedding"])
                print(f"  [OK] {os.path.basename(img_path)}")
        except Exception as e:
            print(f"  [ERROR] {os.path.basename(img_path)} - {e}")

    if embeddings:
        encodings_db[person_name] = embeddings
        print(f"  -> {len(embeddings)} embeddings computed for '{person_name}'")

# Save to disk
with open(ENCODINGS_FILE, "wb") as f:
    pickle.dump(encodings_db, f)

print(f"\n[DONE] Saved {sum(len(v) for v in encodings_db.values())} embeddings "
      f"for {len(encodings_db)} person(s) -> '{ENCODINGS_FILE}'")
print("Run vision_agent.py — it will auto-load this cache for faster startup.")
