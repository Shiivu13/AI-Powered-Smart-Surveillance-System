import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

img_path = "alert_frame.jpg" if os.path.exists("alert_frame.jpg") else "dummy.jpg"
print(f"Testing with: {img_path}")

with open(img_path, "rb") as f:
    image_bytes = f.read()

image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

prompt = (
    "Analyze this image. Reply ONLY with valid JSON, no markdown. "
    'Format: {"threat_status": "unknown_threat", "confidence": 0.9, '
    '"reason": "...", "student_activity": "Focused", "focus_score": 75}'
)

MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

response = None
used_model = None
for model_name in MODELS_TO_TRY:
    try:
        print(f"Trying {model_name}...", end=" ")
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, image_part]
        )
        used_model = model_name
        print("OK!")
        break
    except Exception as e:
        print(f"Failed ({str(e)[:60]})")

if response:
    print(f"\n=== GEMINI RESPONSE ({used_model}) ===")
    print(response.text)
    print("=" * 40)
else:
    print("\nAll models failed.")
