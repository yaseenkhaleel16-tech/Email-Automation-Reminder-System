import csv
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.config import get_settings
from src.reporter import setup_logger
from src.scheduler import run_batch_once

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUTS_DIR = BASE_DIR / "outputs"
LOGS_DIR = BASE_DIR / "logs"

LOGGER = setup_logger(LOGS_DIR)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def get_state() -> dict:
    settings = get_settings()
    contacts = _read_csv(DATA_DIR / "contacts.csv")
    reminders = _read_csv(DATA_DIR / "reminders.csv")
    tmpl_path = TEMPLATES_DIR / "reminder_email.txt"
    template_text = tmpl_path.read_text(encoding="utf-8") if tmpl_path.exists() else ""

    reports = sorted(OUTPUTS_DIR.glob("reminder_report_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest_rows = _read_csv(reports[0]) if reports else []
    latest_name = reports[0].name if reports else "None yet"

    log_path = LOGS_DIR / "automation.log"
    logs = log_path.read_text(encoding="utf-8").splitlines()[-40:] if log_path.exists() else []

    return {
        "contacts": contacts,
        "reminders": reminders,
        "template": template_text,
        "latest_report_name": latest_name,
        "latest_report_rows": latest_rows,
        "logs": logs,
        "smtp_configured": bool(settings.smtp_user and settings.smtp_pass),
    }


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Email Automation & Reminder Dashboard</title>
  <style>
    :root { --bg:#0f172a; --panel:#1e293b; --alt:#162032; --border:#334155; --text:#f1f5f9; --muted:#94a3b8; --blue:#3b82f6; --green:#10b981; --red:#ef4444; --amber:#f59e0b; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:var(--bg); color:var(--text); }
    header { background:var(--panel); border-bottom:1px solid var(--border); padding:16px 24px; display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:12px; }
    header h1 { margin:0; font-size:20px; }
    header p { margin:4px 0 0; color:var(--muted); font-size:13px; }
    .actions { display:flex; gap:10px; flex-wrap:wrap; }
    button { border:none; border-radius:8px; padding:10px 15px; font-weight:600; font-size:13px; cursor:pointer; }
    .btn-blue { background:var(--blue); color:#fff; }
    .btn-green { background:#059669; color:#fff; }
    .btn-gray { background:#334155; color:#fff; }
    .container { max-width:1300px; margin:0 auto; padding:22px; }
    .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:20px; }
    .kpi { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:16px; }
    .kpi .lbl { color:var(--muted); font-size:12px; text-transform:uppercase; }
    .kpi .val { font-size:26px; font-weight:700; margin-top:6px; }
    .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
    @media(max-width:920px){ .grid-2{ grid-template-columns:1fr; } }
    .card { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:18px; margin-bottom:18px; }
    .card h2 { margin:0 0 12px; font-size:16px; display:flex; justify-content:space-between; align-items:center; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); }
    th { color:var(--muted); background:var(--alt); }
    .badge { padding:3px 8px; border-radius:999px; font-size:11px; font-weight:700; }
    .ok { background:rgba(16,185,129,.18); color:#34d399; }
    .fail { background:rgba(239,68,68,.18); color:#f87171; }
    .warn { background:rgba(245,158,11,.18); color:#fbbf24; }
    .form-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:8px; margin-top:12px; }
    input, select, textarea { width:100%; background:#0f172a; border:1px solid var(--border); color:var(--text); padding:8px 10px; border-radius:8px; font-size:13px; }
    textarea { font-family:Consolas,monospace; min-height:210px; }
    pre { background:#090d16; border:1px solid var(--border); border-radius:8px; padding:12px; font-size:12px; max-height:220px; overflow:auto; margin:0; color:#cbd5e1; }
    .toast { position:fixed; bottom:18px; right:18px; background:var(--panel); border:1px solid var(--blue); padding:12px 16px; border-radius:10px; display:none; font-size:13px; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Email Automation & Reminder Dashboard</h1>
      <p>Zero-Dependency Local Web UI • Contacts, Reminders, Templates & CSV Audit Reports</p>
    </div>
    <div class="actions">
      <button class="btn-blue" onclick="runBatch(true)">▶ Run Dry-Run Simulation</button>
      <button class="btn-green" onclick="runBatch(false)">✉ Send Live SMTP Batch</button>
      <button class="btn-gray" onclick="loadState()">↻ Refresh</button>
    </div>
  </header>
  <div class="container">
    <div class="kpis">
      <div class="kpi"><div class="lbl">Contacts</div><div class="val" id="k-contacts">0</div></div>
      <div class="kpi"><div class="lbl">Reminders</div><div class="val" id="k-reminders">0</div></div>
      <div class="kpi"><div class="lbl">Last Run Sent</div><div class="val" style="color:var(--green)" id="k-sent">0</div></div>
      <div class="kpi"><div class="lbl">Last Run Failed</div><div class="val" style="color:var(--red)" id="k-fail">0</div></div>
    </div>

    <div class="card">
      <h2><span>Latest Report (<span id="rep-name">None</span>)</span><span class="badge warn" id="smtp-badge">Status</span></h2>
      <div style="overflow-x:auto">
        <table>
          <thead><tr><th>ID</th><th>Recipient</th><th>Email</th><th>Subject</th><th>Status</th><th>Detail</th></tr></thead>
          <tbody id="rep-body"></tbody>
        </table>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>Contacts (data/contacts.csv)</h2>
        <div style="overflow-x:auto;max-height:220px">
          <table><thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Dept</th></tr></thead><tbody id="c-body"></tbody></table>
        </div>
        <form class="form-grid" onsubmit="addContact(event)">
          <input id="c-name" placeholder="Name" required />
          <input id="c-email" placeholder="email@example.com" required />
          <input id="c-role" placeholder="Role" />
          <input id="c-dept" placeholder="Department" />
          <button class="btn-blue" type="submit">+ Add Contact</button>
        </form>
      </div>

      <div class="card">
        <h2>Reminders (data/reminders.csv)</h2>
        <div style="overflow-x:auto;max-height:220px">
          <table><thead><tr><th>ID</th><th>Contact</th><th>Title</th><th>Due</th><th>Priority</th></tr></thead><tbody id="r-body"></tbody></table>
        </div>
        <form class="form-grid" onsubmit="addReminder(event)">
          <select id="r-contact" required></select>
          <input id="r-title" placeholder="Reminder Title" required />
          <input id="r-date" type="date" required />
          <input id="r-time" type="time" value="10:00" required />
          <select id="r-prio"><option>High</option><option selected>Medium</option><option>Low</option></select>
          <input id="r-notes" placeholder="Notes" />
          <button class="btn-blue" type="submit">+ Add Reminder</button>
        </form>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2><span>Template (templates/reminder_email.txt)</span><button class="btn-blue" onclick="saveTemplate()">Save</button></h2>
        <textarea id="tmpl-box"></textarea>
      </div>
      <div class="card">
        <h2>Execution Logs (logs/automation.log)</h2>
        <pre id="log-box">No logs yet.</pre>
      </div>
    </div>
  </div>
  <div class="toast" id="toast"></div>
  <script>
    function toast(m){ const t=document.getElementById('toast'); t.textContent=m; t.style.display='block'; setTimeout(()=>t.style.display='none',3200); }
    async function loadState(){
      const d = await (await fetch('/api/state')).json();
      document.getElementById('k-contacts').textContent = d.contacts.length;
      document.getElementById('k-reminders').textContent = d.reminders.length;
      document.getElementById('k-sent').textContent = d.latest_report_rows.filter(x=>x.status==='SUCCESS').length;
      document.getElementById('k-fail').textContent = d.latest_report_rows.filter(x=>x.status==='FAILED').length;
      document.getElementById('rep-name').textContent = d.latest_report_name;
      const b = document.getElementById('smtp-badge');
      b.textContent = d.smtp_configured ? 'SMTP Ready (.env)' : 'Dry-Run Mode';
      b.className = 'badge ' + (d.smtp_configured ? 'ok' : 'warn');
      document.getElementById('rep-body').innerHTML = d.latest_report_rows.map(r=>`<tr><td>${r.reminder_id}</td><td>${r.recipient_name}</td><td>${r.recipient_email}</td><td>${r.subject}</td><td><span class="badge ${r.status==='SUCCESS'?'ok':'fail'}">${r.status}</span></td><td>${r.detail}</td></tr>`).join('') || '<tr><td colspan="6">Click Run Dry-Run Simulation to start.</td></tr>';
      document.getElementById('c-body').innerHTML = d.contacts.map(c=>`<tr><td>${c.contact_id}</td><td>${c.name}</td><td>${c.email}</td><td>${c.role}</td><td>${c.department}</td></tr>`).join('');
      document.getElementById('r-contact').innerHTML = d.contacts.map(c=>`<option value="${c.contact_id}">${c.contact_id} - ${c.name}</option>`).join('');
      document.getElementById('r-body').innerHTML = d.reminders.map(r=>`<tr><td>${r.reminder_id}</td><td>${r.contact_id}</td><td>${r.reminder_title}</td><td>${r.due_date} ${r.due_time}</td><td>${r.priority}</td></tr>`).join('');
      document.getElementById('tmpl-box').value = d.template;
      const lb = document.getElementById('log-box'); lb.textContent = d.logs.join('
') || 'No logs yet.'; lb.scrollTop = lb.scrollHeight;
    }
    async function runBatch(dry){
      toast(dry ? 'Running dry-run...' : 'Sending live SMTP batch...');
      const r = await (await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dry_run:dry})})).json();
      toast(`Done: ${r.success} succeeded, ${r.failed} failed`);
      await loadState();
    }
    async function addContact(e){
      e.preventDefault();
      await fetch('/api/contacts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:document.getElementById('c-name').value,email:document.getElementById('c-email').value,role:document.getElementById('c-role').value||'Member',department:document.getElementById('c-dept').value||'General'})});
      e.target.reset(); toast('Contact saved'); await loadState();
    }
    async function addReminder(e){
      e.preventDefault();
      await fetch('/api/reminders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contact_id:document.getElementById('r-contact').value,reminder_title:document.getElementById('r-title').value,due_date:document.getElementById('r-date').value,due_time:document.getElementById('r-time').value,priority:document.getElementById('r-prio').value,notes:document.getElementById('r-notes').value||'Added from dashboard'})});
      e.target.reset(); toast('Reminder saved'); await loadState();
    }
    async function saveTemplate(){
      await fetch('/api/template',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({template:document.getElementById('tmpl-box').value})});
      toast('Template saved');
    }
    loadState();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, data: dict, status: int = 200):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            raw = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/api/state":
            self._json(get_state())
        else:
            self.send_error(404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        data = self._body()
        if path == "/api/run":
            settings = get_settings(dry_run_override=bool(data.get("dry_run", True)))
            report_path, records = run_batch_once(BASE_DIR, settings, LOGGER)
            self._json({
                "report_file": report_path.name,
                "success": sum(1 for r in records if r["status"] == "SUCCESS"),
                "failed": sum(1 for r in records if r["status"] == "FAILED"),
            })
        elif path == "/api/contacts":
            p = DATA_DIR / "contacts.csv"
            rows = _read_csv(p)
            rows.append({
                "contact_id": f"C{len(rows)+1:03d}",
                "name": data.get("name", "").strip(),
                "email": data.get("email", "").strip(),
                "role": data.get("role", "Member").strip(),
                "department": data.get("department", "General").strip(),
                "active": "true",
            })
            _write_csv(p, ["contact_id", "name", "email", "role", "department", "active"], rows)
            self._json({"ok": True})
        elif path == "/api/reminders":
            p = DATA_DIR / "reminders.csv"
            rows = _read_csv(p)
            rows.append({
                "reminder_id": f"R{len(rows)+1:03d}",
                "contact_id": data.get("contact_id", "").strip(),
                "reminder_title": data.get("reminder_title", "").strip(),
                "due_date": data.get("due_date", "").strip(),
                "due_time": data.get("due_time", "").strip(),
                "priority": data.get("priority", "Medium").strip(),
                "notes": data.get("notes", "").strip(),
                "status": "pending",
            })
            _write_csv(p, ["reminder_id", "contact_id", "reminder_title", "due_date", "due_time", "priority", "notes", "status"], rows)
            self._json({"ok": True})
        elif path == "/api/template":
            (TEMPLATES_DIR / "reminder_email.txt").write_text(data.get("template", ""), encoding="utf-8")
            self._json({"ok": True})
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return


def main():
    settings = get_settings()
    port = settings.dashboard_port
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Dashboard running at: http://127.0.0.1:{port}")
    print("Open this URL in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
