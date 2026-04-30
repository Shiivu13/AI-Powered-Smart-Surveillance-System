# 🛡️ AI-Powered Smart Surveillance System
### EdTech Security + Student Behavioral Analysis Engine

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Celery](https://img.shields.io/badge/Celery-5.6-brightgreen?logo=celery)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-7.0-red?logo=redis)](https://redis.io)
[![Supabase](https://img.shields.io/badge/Supabase-Cloud-3ECF8E?logo=supabase)](https://supabase.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)

---

## 🧠 What It Does

A **production-grade, real-time surveillance system** that combines computer vision, 
face recognition, and multimodal AI to provide:

- 🔍 **Real-time person detection** via YOLOv8
- 👤 **Face whitelisting** — distinguishes authorized users from intruders
- 🎓 **EdTech behavioral analysis** — detects student focus, pen grasping, distraction
- ☁️ **Cloud AI pipeline** — Gemini 1.5 Flash for deep analysis
- 📊 **Live analytics dashboard** — real-time charts and event logs
- 🔐 **API key authentication** — secured ingestion endpoint
- 🐳 **Fully Dockerized** — one-command deployment

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SMART SURVEILLANCE SYSTEM                             │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────┐
  │         EDGE LAYER               │
  │  ┌────────────────────────────┐  │
  │  │     vision_agent.py        │  │
  │  │                            │  │
  │  │  Webcam → YOLOv8           │  │
  │  │  Person Detected?          │  │
  │  │       │                    │  │
  │  │  ┌────▼────────────────┐   │  │
  │  │  │  DeepFace (Thread)  │   │  │
  │  │  │  Facenet + Cosine   │   │  │
  │  │  └────────────────────-┘   │  │
  │  │       │           │        │  │
  │  │  AUTHORIZED    UNKNOWN     │  │
  │  │  Green Box ──► Red Box     │  │
  │  │  Skip API      Save Frame  │  │
  │  │                   │        │  │
  │  └───────────────────┼────────┘  │
  │                       │          │
  └───────────────────────┼──────────┘
                           │ HTTP POST (X-API-Key)
                           ▼
  ┌────────────────────────────────────┐
  │          API LAYER                 │
  │   FastAPI — backend/main.py        │
  │                                    │
  │   POST /v1/ingest-threat           │
  │   GET  /dashboard    (Analytics)   │
  │   GET  /api/logs     (JSON)        │
  │   GET  /api/status                 │
  │                                    │
  │   Saves frame to: captures/        │
  │   Pushes job to Celery via Redis   │
  └────────────┬───────────────────────┘
               │ Job Queue
               ▼
  ┌────────────────────────────────────┐
  │         MESSAGE BROKER             │
  │           Redis 7.0                │
  │        localhost:6379              │
  └────────────┬───────────────────────┘
               │ Task
               ▼
  ┌────────────────────────────────────┐
  │         WORKER LAYER               │
  │   Celery — backend/worker.py       │
  │                                    │
  │   1. Upload image to Supabase      │
  │      Storage (threat-images/)      │
  │                                    │
  │   2. Call Opal Webhook →           │
  │      Gemini 1.5 Flash              │
  │      ├─ Security Analysis          │
  │      └─ EdTech Behavioral          │
  │         (Focus Score, Activity)    │
  │                                    │
  │   3. Insert result to              │
  │      Supabase DB (security_logs)   │
  └────────────┬───────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │         CLOUD LAYER                │
  │                                    │
  │   ┌──────────────────────────┐     │
  │   │  Supabase Storage        │     │
  │   │  Bucket: threat-images   │     │
  │   └──────────────────────────┘     │
  │   ┌──────────────────────────┐     │
  │   │  Supabase PostgreSQL     │     │
  │   │  Table: security_logs    │     │
  │   │  ─ threat_status         │     │
  │   │  ─ confidence_score      │     │
  │   │  ─ reason                │     │
  │   │  ─ image_url             │     │
  │   │  ─ student_activity      │     │
  │   │  ─ focus_score           │     │
  │   └──────────────────────────┘     │
  └────────────────────────────────────┘
               │
               ▼
  ┌────────────────────────────────────┐
  │       ANALYTICS DASHBOARD          │
  │   http://localhost:8000/dashboard  │
  │                                    │
  │   📊 Auth vs Unknown Donut Chart   │
  │   🎓 Student Activity Chart        │
  │   ⏰ Peak Alert Hours Bar Chart    │
  │   📋 Real-time Event Log Table     │
  └────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Option A — Local (Manual)

```bash
# 1. Clone & setup
git clone https://github.com/Shiivu13/AI-Powered-Smart-Surveillance-System
cd smart-surveillance-system
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env with your Supabase keys

# 3. Start Redis
docker run -d -p 6379:6379 redis

# 4. Start FastAPI
uvicorn backend.main:app --port 8000

# 5. Start Celery Worker
celery -A backend.worker worker --loglevel=info -P solo

# 6. Enroll known faces
python encode_faces.py

# 7. Start Surveillance
python vision_agent.py

# 8. View Dashboard
open http://localhost:8000/dashboard
```

### Option B — Docker (One Command)

```bash
docker-compose up --build
```

---

## 📁 Project Structure

```
smart-surveillance-system/
│
├── vision_agent.py          # Edge: Camera + YOLO + DeepFace
├── encode_faces.py          # Pre-compute face embeddings cache
│
├── backend/
│   ├── main.py              # FastAPI: Ingestion API + Dashboard
│   └── worker.py            # Celery: AI Pipeline Worker
│
├── known_faces/             # Face enrollment database
│   └── shiivu/              # One folder per person
│
├── captures/                # Saved alert frames
├── face_encodings.pkl       # Pre-computed embeddings cache
│
├── docker-compose.yml       # Full stack orchestration
├── Dockerfile               # Container build spec
├── requirements.txt         # Python dependencies
├── .env                     # Credentials (gitignored)
└── README.md
```

---

## 🎓 EdTech Features (Nesoi AI Context)

The system goes beyond security — it analyzes **student behavioral signals**:

| Signal | Detection | Output |
|---|---|---|
| Writing / Pen Grasping | Hand pose via Gemini Vision | `Active Learning` |
| Facing screen | Face orientation | `Focused` |
| Looking away | Gaze direction | `Distracted` |
| Head down / Sleeping | Pose estimation | Focus Score < 20 |

**Interview Talking Point:**
> *"Maine multimodal logic ko tune kiya hai taaki wo EdTech-specific context ko samajh sake — jaise pen grasping, student posture, aur gaze direction — sirf security nahi. Is system ka focus score ek real quantitative metric hai jo classroom engagement measure karta hai."*

---

## 🔐 API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/dashboard` | None | Analytics Dashboard UI |
| `GET` | `/api/logs` | None | JSON security event logs |
| `GET` | `/api/status` | None | System health check |
| `POST` | `/v1/ingest-threat` | `X-API-Key` | Ingest alert frame |

**Example Request:**
```bash
curl -X POST http://localhost:8000/v1/ingest-threat \
  -H "X-API-Key: surv-secret-key-2026" \
  -F "file=@alert_frame.jpg"
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Object Detection | YOLOv8n (Ultralytics) |
| Face Recognition | DeepFace (Facenet + Cosine) |
| AI Analysis | Gemini 1.5 Flash via Opal |
| API Framework | FastAPI + Uvicorn |
| Task Queue | Celery 5.6 |
| Message Broker | Redis 7.0 |
| Database | Supabase PostgreSQL |
| Storage | Supabase Storage |
| Dashboard | Chart.js + Vanilla JS |
| Containerization | Docker + Docker Compose |
| Language | Python 3.12 |

---

## 👤 Author

**Shiivu** — AI/ML Engineer  
[GitHub](https://github.com/Shiivu13) · [LinkedIn](#)
