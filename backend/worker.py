import os
import json
import base64
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

def safe_print(msg, end="\n"):
    try:
        print(msg, end=end, flush=True)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'), end=end, flush=True)

REDIS_URL      = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUCKET_NAME    = os.getenv("BUCKET_NAME", "threat-images")

celery_app = Celery("surveillance_tasks", broker=REDIS_URL, backend=REDIS_URL)

# ── Supabase client ───────────────────────────────────────────────────────────
supabase = None
try:
    from supabase import create_client
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    pass

# ── Gemini client ─────────────────────────────────────────────────────────────
gemini_client = None
try:
    from google import genai
    if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        safe_print("[WORKER] Gemini 2.5 Flash ready.")
    else:
        safe_print("[WORKER] Gemini key not set — AI analysis will be skipped.")
except Exception as e:
    safe_print(f"[WORKER] Gemini init failed: {e}")

GEMINI_PROMPT = """
You are an AI security and behavioral analysis agent for an EdTech surveillance platform.
Analyze the provided image and return a JSON response ONLY — no markdown, no explanation.

Perform TWO tasks:

1. SECURITY ANALYSIS:
   - Is the person authorized or an unknown intruder?
   - threat_status options: "authorized", "unknown_threat", "potential_threat"

2. STUDENT BEHAVIOR (EdTech):
   - If student is writing / holding a pen → student_activity: "Active Learning"
   - If student is looking at screen/board → student_activity: "Focused"
   - If student is looking away / distracted → student_activity: "Distracted"
   - If student is sleeping / head down → student_activity: "Sleeping", focus_score < 15
   - focus_score: integer 0-100 (100 = fully focused, 0 = completely disengaged)

Respond STRICTLY with this JSON format:
{
  "threat_status": "unknown_threat",
  "confidence": 0.92,
  "reason": "Person detected near restricted area.",
  "student_activity": "Active Learning",
  "focus_score": 78
}
"""

def analyze_with_gemini(image_path: str) -> dict:
    """Send image to Gemini 2.5 Flash for security + behavioral analysis."""
    if not gemini_client:
        return {
            "threat_status": "unknown_threat",
            "confidence": 0.0,
            "reason": "Gemini key not configured — set GEMINI_API_KEY in .env",
            "student_activity": None,
            "focus_score": None
        }
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        from google.genai import types
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        import time
        MODELS = ["gemini-2.5-flash", "gemini-1.5-flash"]
        response = None
        for model_name in MODELS:
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=[GEMINI_PROMPT, image_part]
                )
                break
            except Exception as e:
                safe_print(f"  [Gemini] {model_name} failed: {str(e)[:100]}")
                time.sleep(3)  # Wait longer to avoid rate limit
                continue

        if not response:
            return {"threat_status": "unknown_threat", "confidence": 0.0,
                    "reason": "All Gemini models unavailable", "student_activity": None, "focus_score": None}

        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        return result

    except json.JSONDecodeError as e:
        safe_print(f"[Gemini] JSON parse error: {e} | raw: {response.text[:200]}")
        return {"threat_status": "unknown_threat", "confidence": 0.5,
                "reason": "AI response parse error", "student_activity": None, "focus_score": None}
    except Exception as e:
        safe_print(f"[Gemini] Error: {e}")
        return {"threat_status": "unknown_threat", "confidence": 0.0,
                "reason": f"Gemini error: {str(e)}", "student_activity": None, "focus_score": None}


@celery_app.task(name="process_surveillance_frame", bind=True)
def process_surveillance_frame(self, job_id: str, image_path: str, status: str = "unknown_threat"):
    if not supabase:
        safe_print("[WORKER] Supabase not initialized — skipping.")
        return {"status": "failed", "reason": "Supabase not connected"}

    filename   = os.path.basename(image_path)
    public_url = ""

    # ── STEP 1: Upload to Supabase Storage ───────────────────────────────────
    try:
        safe_print(f"[{job_id[:8]}] Uploading to Storage... ", end="")
        with open(image_path, "rb") as f:
            file_bytes = f.read()

        storage_path = f"{job_id}_{filename}"
        supabase.storage.from_(BUCKET_NAME).upload(storage_path, file_bytes)
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)
        safe_print("Done.")
    except Exception as e:
        safe_print(f"Failed: {e}")
        return {"status": "failed", "reason": f"Storage upload failed: {e}"}

    # ── STEP 2: Gemini AI Analysis ────────────────────────────────────────────
    safe_print(f"[{job_id[:8]}] Analyzing with Gemini... ", end="")
    ai = analyze_with_gemini(image_path)
    safe_print("Done.")
    
    # Override threat_status if vision agent provided a definitive one (like authorized)
    final_status = status if status == "authorized" else ai.get("threat_status", "unknown_threat")
    
    # For authorized users: set meaningful defaults if Gemini is unavailable
    if final_status == "authorized" and ai.get("reason", "").startswith("All Gemini"):
        ai["reason"]           = "Known person verified by FaceNet facial recognition."
        ai["student_activity"] = ai.get("student_activity") or "Focused"
        ai["focus_score"]      = ai.get("focus_score")      or 70
    
    safe_print(f"  -> Status: {final_status} | "
               f"Activity: {ai.get('student_activity')} | "
               f"Focus: {ai.get('focus_score')}")

    # ── STEP 3: Save to Supabase DB ───────────────────────────────────────────
    try:
        safe_print(f"[{job_id[:8]}] Saving to DB... ", end="")
        row = {
            "threat_status":    final_status,
            "confidence_score": float(ai.get("confidence", 0.0)) if final_status != "authorized" else 1.0,
            "reason":           ai.get("reason", ""),
            "image_url":        public_url,
        }
        # Add EdTech fields only if present (backward compatible)
        if ai.get("student_activity") is not None:
            row["student_activity"] = ai["student_activity"]
        if ai.get("focus_score") is not None:
            row["focus_score"] = int(ai["focus_score"])

        # Try inserting with EdTech fields first
        try:
            supabase.table("security_logs").insert(row).execute()
        except Exception:
            # If EdTech columns don't exist yet, insert base row only
            base_row = {
                "threat_status":    row["threat_status"],
                "confidence_score": row["confidence_score"],
                "reason":           row["reason"],
                "image_url":        row["image_url"],
            }
            supabase.table("security_logs").insert(base_row).execute()
        safe_print("Done.")
    except Exception as e:
        safe_print(f"Failed: {e}")

    return {"status": "processed", "analysis": ai}
