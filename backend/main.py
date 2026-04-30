import os
import uuid
from collections import defaultdict
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import HTMLResponse
from celery import Celery

load_dotenv()

REDIS_URL      = os.getenv("REDIS_URL", "redis://localhost:6379/0")
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "surv-secret-key-2026")
CAPTURES_DIR   = os.getenv("CAPTURES_DIR", "captures")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")

os.makedirs(CAPTURES_DIR, exist_ok=True)

celery_app = Celery("surveillance_tasks", broker=REDIS_URL, backend=REDIS_URL)

supabase = None
try:
    from supabase import create_client
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    pass

app = FastAPI(title="Smart Surveillance API", version="3.0.0")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def require_api_key(key: str = Security(api_key_header)):
    if key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key.")
    return key

# ── Dashboard HTML ─────────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart Surveillance — Analytics</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:'Inter',sans-serif;background:#080c18;color:#e2e8f0;min-height:100vh}
    header{
      background:linear-gradient(135deg,#0f1729 0%,#080c18 100%);
      border-bottom:1px solid #1a2540;padding:16px 28px;
      display:flex;align-items:center;justify-content:space-between
    }
    .brand{display:flex;align-items:center;gap:10px}
    .brand-icon{width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:16px}
    .brand h1{font-size:1.1rem;font-weight:700;color:#f1f5f9}
    .brand span{font-size:0.7rem;color:#64748b;background:#1a2540;padding:2px 8px;border-radius:4px;margin-left:8px}
    .header-right{display:flex;align-items:center;gap:12px}
    .live-pill{display:flex;align-items:center;gap:5px;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);color:#f87171;padding:4px 12px;border-radius:20px;font-size:.72rem;font-weight:600}
    .live-dot{width:6px;height:6px;border-radius:50%;background:#ef4444;animation:pulse 1s infinite}
    .refresh-status{font-size:.72rem;color:#475569}
    @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(1.3)}}

    /* Stats */
    .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;padding:22px 28px 0}
    .stat{background:#0d1321;border:1px solid #1a2540;border-radius:12px;padding:18px;position:relative;overflow:hidden;transition:transform .2s,border-color .2s}
    .stat:hover{transform:translateY(-2px);border-color:#3b82f6}
    .stat-accent{position:absolute;top:0;left:0;right:0;height:3px}
    .stat-label{font-size:.68rem;color:#64748b;font-weight:500;text-transform:uppercase;letter-spacing:.06em}
    .stat-val{font-size:1.9rem;font-weight:700;color:#f1f5f9;margin-top:6px;line-height:1}
    .stat-sub{font-size:.7rem;color:#475569;margin-top:4px}

    /* Charts row */
    .charts-row{display:grid;grid-template-columns:1fr 1fr 1.6fr;gap:14px;padding:18px 28px}
    .chart-card{background:#0d1321;border:1px solid #1a2540;border-radius:12px;padding:18px}
    .card-title{font-size:.8rem;font-weight:600;color:#94a3b8;margin-bottom:14px;text-transform:uppercase;letter-spacing:.05em}
    .chart-wrap{position:relative;height:180px}

    /* Focus gauge */
    .gauge-wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;height:180px;gap:8px}
    .gauge-num{font-size:3rem;font-weight:700;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1}
    .gauge-label{font-size:.75rem;color:#64748b;font-weight:500}
    .gauge-bar{width:100%;background:#1a2540;border-radius:4px;height:6px;overflow:hidden;margin-top:4px}
    .gauge-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#3b82f6,#8b5cf6);transition:width .6s ease}

    /* Table */
    .table-section{padding:0 28px 28px}
    .section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
    .section-title{font-size:.88rem;font-weight:600;color:#f1f5f9}
    .filter-btns{display:flex;gap:6px}
    .filter-btn{background:#1a2540;border:1px solid #243450;color:#64748b;padding:4px 12px;border-radius:6px;cursor:pointer;font-size:.72rem;font-family:'Inter',sans-serif;transition:all .2s}
    .filter-btn.active,.filter-btn:hover{background:#2563eb;color:#fff;border-color:#2563eb}
    .tbl-wrap{background:#0d1321;border:1px solid #1a2540;border-radius:12px;overflow:hidden}
    table{width:100%;border-collapse:collapse}
    thead th{background:#080c18;padding:10px 14px;text-align:left;font-size:.67rem;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:.07em;border-bottom:1px solid #1a2540}
    tbody tr{border-bottom:1px solid #131c2f;transition:background .15s}
    tbody tr:last-child{border:none}
    tbody tr:hover{background:rgba(37,99,235,.05)}
    tbody td{padding:12px 14px;font-size:.82rem;color:#cbd5e1;vertical-align:middle}
    .badge{display:inline-flex;align-items:center;gap:3px;padding:2px 9px;border-radius:20px;font-size:.68rem;font-weight:600}
    .badge.threat {background:rgba(239,68,68,.12);color:#f87171;border:1px solid rgba(239,68,68,.2)}
    .badge.safe   {background:rgba(34,197,94,.12);color:#4ade80;border:1px solid rgba(34,197,94,.2)}
    .badge.warn   {background:rgba(245,158,11,.12);color:#fbbf24;border:1px solid rgba(245,158,11,.2)}
    .badge.info   {background:rgba(59,130,246,.12);color:#60a5fa;border:1px solid rgba(59,130,246,.2)}
    .thumb{width:44px;height:44px;border-radius:8px;object-fit:cover}
    .no-img{width:44px;height:44px;border-radius:8px;background:#1a2540;display:flex;align-items:center;justify-content:center;font-size:.6rem;color:#475569}
    .conf-bar{background:#1a2540;border-radius:3px;height:3px;width:70px;overflow:hidden;margin-top:4px}
    .conf-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#3b82f6,#8b5cf6)}
    .activity-chip{font-size:.68rem;color:#a78bfa;background:rgba(139,92,246,.1);border:1px solid rgba(139,92,246,.2);padding:1px 7px;border-radius:4px}
    .empty{text-align:center;padding:40px;color:#475569;font-size:.85rem}
  </style>
</head>
<body>

<header>
  <div class="brand">
    <div class="brand-icon">🛡️</div>
    <h1>Smart Surveillance<span>EdTech Edition</span></h1>
  </div>
  <div class="header-right">
    <span class="refresh-status" id="last-refresh">Loading...</span>
    <div class="live-pill"><div class="live-dot"></div>LIVE</div>
  </div>
</header>

<!-- Stats Row -->
<div class="stats">
  <div class="stat">
    <div class="stat-accent" style="background:linear-gradient(90deg,#ef4444,#dc2626)"></div>
    <div class="stat-label">Total Events</div>
    <div class="stat-val" id="s-total">—</div>
    <div class="stat-sub">All security logs</div>
  </div>
  <div class="stat">
    <div class="stat-accent" style="background:linear-gradient(90deg,#ef4444,#f97316)"></div>
    <div class="stat-label">Unknown Threats</div>
    <div class="stat-val" id="s-threats">—</div>
    <div class="stat-sub">Unauthorized detections</div>
  </div>
  <div class="stat">
    <div class="stat-accent" style="background:linear-gradient(90deg,#22c55e,#16a34a)"></div>
    <div class="stat-label">Authorized</div>
    <div class="stat-val" id="s-auth">—</div>
    <div class="stat-sub">Known persons</div>
  </div>
  <div class="stat">
    <div class="stat-accent" style="background:linear-gradient(90deg,#8b5cf6,#7c3aed)"></div>
    <div class="stat-label">Avg Focus Score</div>
    <div class="stat-val" id="s-focus">—</div>
    <div class="stat-sub">Student engagement</div>
  </div>
  <div class="stat">
    <div class="stat-accent" style="background:linear-gradient(90deg,#3b82f6,#2563eb)"></div>
    <div class="stat-label">AI Confidence</div>
    <div class="stat-val" id="s-conf">—</div>
    <div class="stat-sub">Avg detection accuracy</div>
  </div>
  <div class="stat">
    <div class="stat-accent" style="background:linear-gradient(90deg,#f59e0b,#d97706)"></div>
    <div class="stat-label">Last Alert</div>
    <div class="stat-val" id="s-last" style="font-size:1rem;padding-top:8px">—</div>
    <div class="stat-sub">Most recent event</div>
  </div>
</div>

<!-- Charts Row -->
<div class="charts-row">
  <!-- Donut: Auth vs Unknown -->
  <div class="chart-card">
    <div class="card-title">Authorized vs Unknown</div>
    <div class="chart-wrap"><canvas id="donutChart"></canvas></div>
  </div>
  <!-- Student Activity Breakdown -->
  <div class="chart-card">
    <div class="card-title">Student Activity</div>
    <div class="chart-wrap"><canvas id="activityChart"></canvas></div>
  </div>
  <!-- Peak Threat Hours -->
  <div class="chart-card">
    <div class="card-title">Peak Alert Hours</div>
    <div class="chart-wrap"><canvas id="hoursChart"></canvas></div>
  </div>
</div>

<!-- Logs Table -->
<div class="table-section">
  <div class="section-header">
    <div class="section-title">Security Event Log</div>
    <div class="filter-btns">
      <button class="filter-btn active" onclick="filterLogs('all',this)">All</button>
      <button class="filter-btn" onclick="filterLogs('threat',this)">Threats</button>
      <button class="filter-btn" onclick="filterLogs('authorized',this)">Authorized</button>
    </div>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>Frame</th><th>Status</th><th>Confidence</th>
          <th>Student Activity</th><th>Reason</th><th>Time</th>
        </tr>
      </thead>
      <tbody id="logs-body">
        <tr><td colspan="6" class="empty">Loading events...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
  let allLogs = [];
  let donutChart, activityChart, hoursChart;

  const CHART_DEFAULTS = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } } }
  };

  function initCharts() {
    // Donut
    donutChart = new Chart(document.getElementById('donutChart'), {
      type: 'doughnut',
      data: { labels: ['Authorized','Unknown Threat','Potential Threat'],
              datasets: [{ data: [0,0,0], backgroundColor: ['#22c55e','#ef4444','#f59e0b'],
                borderWidth: 0, hoverOffset: 6 }] },
      options: { ...CHART_DEFAULTS, cutout: '68%' }
    });

    // Activity
    activityChart = new Chart(document.getElementById('activityChart'), {
      type: 'doughnut',
      data: { labels: ['Active Learning','Focused','Distracted','Unknown'],
              datasets: [{ data: [0,0,0,0],
                backgroundColor: ['#8b5cf6','#3b82f6','#ef4444','#475569'],
                borderWidth: 0, hoverOffset: 6 }] },
      options: { ...CHART_DEFAULTS, cutout: '68%' }
    });

    // Hours bar
    hoursChart = new Chart(document.getElementById('hoursChart'), {
      type: 'bar',
      data: {
        labels: Array.from({length:24}, (_,i) => i+'h'),
        datasets: [{
          label: 'Alerts',
          data: new Array(24).fill(0),
          backgroundColor: 'rgba(59,130,246,0.6)',
          borderColor: '#3b82f6',
          borderWidth: 1,
          borderRadius: 4
        }]
      },
      options: {
        ...CHART_DEFAULTS,
        scales: {
          x: { ticks: { color:'#475569', font:{size:9} }, grid: { color:'#131c2f' } },
          y: { ticks: { color:'#475569', stepSize:1 }, grid: { color:'#131c2f' }, beginAtZero:true }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  function updateCharts(logs, stats) {
    // Donut
    donutChart.data.datasets[0].data = [stats.authorized_count, stats.threat_count, stats.potential_count];
    donutChart.update();

    // Activity
    const ac = {active_learning:0, focused:0, distracted:0, unknown:0};
    logs.forEach(l => {
      const a = (l.student_activity||'').toLowerCase();
      if (a.includes('active')) ac.active_learning++;
      else if (a.includes('focus')) ac.focused++;
      else if (a.includes('distract')) ac.distracted++;
      else ac.unknown++;
    });
    activityChart.data.datasets[0].data = [ac.active_learning, ac.focused, ac.distracted, ac.unknown];
    activityChart.update();

    // Hours
    const hourCounts = new Array(24).fill(0);
    logs.forEach(l => {
      if (l.created_at) hourCounts[new Date(l.created_at).getHours()]++;
    });
    hoursChart.data.datasets[0].data = hourCounts;
    hoursChart.update();
  }

  function badgeHtml(status) {
    const s = (status||'').toLowerCase();
    if (s.includes('unknown_threat')||s.includes('potential')) return `<span class="badge threat">⚠ ${status}</span>`;
    if (s.includes('authorized')||s.includes('safe'))           return `<span class="badge safe">✓ ${status}</span>`;
    return `<span class="badge warn">? ${status}</span>`;
  }

  function activityBadge(act) {
    if (!act) return '—';
    return `<span class="activity-chip">${act}</span>`;
  }

  function renderTable(logs) {
    if (!logs.length) {
      document.getElementById('logs-body').innerHTML = '<tr><td colspan="6" class="empty">No events recorded yet.</td></tr>';
      return;
    }
    document.getElementById('logs-body').innerHTML = logs.map(l => {
      const pct = Math.round((l.confidence_score||0)*100);
      const thumb = l.image_url
        ? `<img class="thumb" src="${l.image_url}" onerror="this.outerHTML='<div class=no-img>N/A</div>'">`
        : '<div class="no-img">N/A</div>';
      const ts = l.created_at ? new Date(l.created_at).toLocaleString() : '—';
      return `<tr>
        <td>${thumb}</td>
        <td>${badgeHtml(l.threat_status)}</td>
        <td>
          <div style="font-size:.8rem;font-weight:600">${pct}%</div>
          <div class="conf-bar"><div class="conf-fill" style="width:${pct}%"></div></div>
        </td>
        <td>${activityBadge(l.student_activity)}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#64748b;font-size:.78rem">${l.reason||'—'}</td>
        <td style="color:#475569;font-size:.75rem">${ts}</td>
      </tr>`;
    }).join('');
  }

  function filterLogs(type, btn) {
    document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    if (type==='all') renderTable(allLogs);
    else if (type==='threat') renderTable(allLogs.filter(l=>(l.threat_status||'').includes('threat')));
    else renderTable(allLogs.filter(l=>(l.threat_status||'').includes('authorized')));
  }

  async function fetchData() {
    try {
      const res  = await fetch('/api/logs');
      const data = await res.json();
      allLogs = data.logs || [];

      // Update stats
      document.getElementById('s-total').textContent   = data.total_count ?? '—';
      document.getElementById('s-threats').textContent = data.threat_count ?? '—';
      document.getElementById('s-auth').textContent    = data.authorized_count ?? '—';
      document.getElementById('s-focus').textContent   = data.avg_focus_score ? data.avg_focus_score+'%' : '—';
      document.getElementById('s-conf').textContent    = data.avg_confidence ? (data.avg_confidence*100).toFixed(0)+'%' : '—';
      document.getElementById('s-last').textContent    = data.last_alert ? new Date(data.last_alert).toLocaleTimeString() : 'None';
      document.getElementById('last-refresh').textContent = 'Updated: ' + new Date().toLocaleTimeString();

      updateCharts(allLogs, data);
      renderTable(allLogs);
    } catch(e) {
      document.getElementById('logs-body').innerHTML = '<tr><td colspan="6" class="empty" style="color:#ef4444">Connection error. Is the server running?</td></tr>';
    }
  }

  initCharts();
  fetchData();
  setInterval(fetchData, 8000);
</script>
</body>
</html>"""

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)

@app.get("/api/logs")
async def get_logs():
    if not supabase:
        return {"logs": [], "total_count": 0, "threat_count": 0, "authorized_count": 0,
                "potential_count": 0, "avg_confidence": 0, "avg_focus_score": 0, "last_alert": None}
    try:
        res  = supabase.table("security_logs").select("*").order("created_at", desc=True).limit(100).execute()
        logs = res.data or []

        total      = len(logs)
        threat_c   = sum(1 for l in logs if "unknown_threat" in (l.get("threat_status") or ""))
        potential_c= sum(1 for l in logs if "potential" in (l.get("threat_status") or ""))
        auth_c     = sum(1 for l in logs if "authorized" in (l.get("threat_status") or ""))
        avg_conf   = round(sum(l.get("confidence_score", 0) for l in logs) / total, 3) if total else 0

        # Focus score (EdTech field — may not exist yet in old rows)
        focus_scores = [l["focus_score"] for l in logs if l.get("focus_score") is not None]
        avg_focus    = round(sum(focus_scores) / len(focus_scores)) if focus_scores else None

        return {
            "logs": logs,
            "total_count": total,
            "threat_count": threat_c,
            "potential_count": potential_c,
            "authorized_count": auth_c,
            "avg_confidence": avg_conf,
            "avg_focus_score": avg_focus,
            "last_alert": logs[0].get("created_at") if logs else None
        }
    except Exception as e:
        return {"logs": [], "error": str(e)}

@app.get("/api/status")
async def status():
    return {"api": "online", "celery_broker": REDIS_URL,
            "supabase": "connected" if supabase else "disconnected"}

@app.post("/v1/ingest-threat", dependencies=[Security(require_api_key)])
async def ingest_threat(file: UploadFile = File(...), status: str = "unknown_threat"):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    job_id    = str(uuid.uuid4())
    ext       = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
    file_path = os.path.join(CAPTURES_DIR, f"{job_id}.{ext}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    task = celery_app.send_task("process_surveillance_frame", args=[job_id, file_path, status])
    return {"status": "accepted", "job_id": job_id, "task_id": task.id,
            "message": "Frame queued for AI analysis."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
