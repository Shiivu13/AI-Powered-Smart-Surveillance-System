import requests
import time

API_URL = "http://127.0.0.1:8000/v1/ingest-threat"
API_KEY = "surv-secret-key-2026"

print("=" * 55)
print("  END-TO-END TEST — Smart Surveillance System")
print("=" * 55)

# Test 1: No API key — should 401
print("\n[TEST 1] Without API key (expect 401)...")
r = requests.post(API_URL,
    files={"file": ("test.jpg", open("dummy.jpg", "rb"), "image/jpeg")})
print(f"  Status  : {r.status_code}  | Expected: 401")
print(f"  Response: {r.json()}")

# Test 2: With valid API key — should 200
print("\n[TEST 2] With valid API key (expect 200)...")
r = requests.post(API_URL,
    headers={"X-API-Key": API_KEY},
    files={"file": ("alert_frame.jpg", open("dummy.jpg", "rb"), "image/jpeg")})
print(f"  Status  : {r.status_code}  | Expected: 200")
d = r.json()
print(f"  job_id  : {d.get('job_id')}")
print(f"  task_id : {d.get('task_id')}")
print(f"  status  : {d.get('status')}")

# Test 3: Check API logs from Supabase
print("\n[TEST 3] Fetching security logs from /api/logs...")
time.sleep(2)
r = requests.get("http://127.0.0.1:8000/api/logs")
s = r.json()
print(f"  Total Events    : {s.get('total_count')}")
print(f"  Unknown Threats : {s.get('threat_count')}")
print(f"  Authorized      : {s.get('authorized_count')}")
print(f"  Avg Confidence  : {s.get('avg_confidence')}")
print(f"  Last Alert      : {s.get('last_alert')}")

print("\n[DONE] All tests complete!")
print("  Dashboard: http://127.0.0.1:8000/dashboard")
print("=" * 55)
