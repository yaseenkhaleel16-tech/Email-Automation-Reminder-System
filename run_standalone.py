import csv, email.utils, logging, os, re, smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

BASE = Path(__file__).resolve().parent
(BASE / "logs").mkdir(exist_ok=True)
(BASE / "outputs").mkdir(exist_ok=True)

env_file = BASE / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

dry_run = os.getenv("DRY_RUN", "true").strip().lower() in {"1", "true", "yes", "on"}
sender_name = os.getenv("SENDER_NAME", "Automation Assistant").strip()
sender_email = os.getenv("SENDER_EMAIL", os.getenv("SMTP_USER", "noreply@example.com")).strip()
smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
smtp_port = int(os.getenv("SMTP_PORT", "465").strip())
smtp_user = os.getenv("SMTP_USER", "").strip()
smtp_pass = os.getenv("SMTP_PASS", "").strip()

logger = logging.getLogger("standalone_mailer")
logger.setLevel(logging.INFO)
logger.handlers.clear()
fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
fh = logging.FileHandler(BASE / "logs" / "automation.log", encoding="utf-8"); fh.setFormatter(fmt)
sh = logging.StreamHandler(); sh.setFormatter(fmt)
logger.addHandler(fh); logger.addHandler(sh)


def valid_email(addr):
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (addr or "").strip()))


def render(tmpl, ctx):
    out = re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", lambda m: str(ctx.get(m.group(1), f"[Missing:{m.group(1)}]")), tmpl)
    lines = out.splitlines()
    subj, body_lines = "Automated Reminder Notification", lines
    if lines and lines[0].lower().startswith("subject:"):
        subj = lines[0].split(":", 1)[1].strip()
        body_lines = lines[1:]
        if body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]
    return subj, "\n".join(body_lines).strip()


def main():
    with open(BASE / "data" / "contacts.csv", encoding="utf-8", newline="") as f:
        contacts = {r["contact_id"]: r for r in csv.DictReader(f) if r.get("active", "true").strip().lower() in {"true", "1", "yes", ""}}

    with open(BASE / "data" / "reminders.csv", encoding="utf-8", newline="") as f:
        reminders = [r for r in csv.DictReader(f) if r.get("status", "pending").strip().lower() in {"pending", "scheduled", ""}]

    tmpl = (BASE / "templates" / "reminder_email.txt").read_text(encoding="utf-8")
    logger.info("Initialized | Mode: %s | Contacts: %d | Reminders: %d", "DRY-RUN" if dry_run else "LIVE-SMTP", len(contacts), len(reminders))

    rows_out = []
    for r in reminders:
        c = contacts.get(r.get("contact_id", ""), {})
        ctx = {
            "contact_id": r.get("contact_id", ""),
            "name": c.get("name") or "Team Member",
            "email": c.get("email", ""),
            "role": c.get("role") or "Team",
            "department": c.get("department") or "General",
            "reminder_id": r.get("reminder_id", ""),
            "reminder_title": r.get("reminder_title", ""),
            "due_date": r.get("due_date", ""),
            "due_time": r.get("due_time", ""),
            "priority": r.get("priority") or "Normal",
            "notes": r.get("notes") or "No additional notes.",
            "sender_name": sender_name,
        }
        subj, body = render(tmpl, ctx)
        to_addr = ctx["email"].strip()
        if not valid_email(to_addr):
            ok, detail = False, f"Invalid recipient email address: '{to_addr}'"
            logger.error(detail)
        elif dry_run:
            ok, detail = True, "DRY_RUN_SIMULATED"
            logger.info("[DRY-RUN] Simulated email to %s | Subject: '%s'", to_addr, subj)
        else:
            try:
                msg = EmailMessage()
                msg["From"] = email.utils.formataddr((sender_name, sender_email))
                msg["To"] = to_addr
                msg["Subject"] = subj
                msg.set_content(body)
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as srv:
                    srv.login(smtp_user, smtp_pass)
                    srv.send_message(msg)
                ok, detail = True, "SENT"
                logger.info("Sent email to %s | Subject: '%s'", to_addr, subj)
            except Exception as exc:
                ok, detail = False, str(exc)
                logger.error("Failed sending to %s: %s", to_addr, exc)

        rows_out.append({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reminder_id": ctx["reminder_id"],
            "contact_id": ctx["contact_id"],
            "recipient_name": ctx["name"],
            "recipient_email": to_addr,
            "reminder_title": ctx["reminder_title"],
            "due_date": ctx["due_date"],
            "due_time": ctx["due_time"],
            "subject": subj,
            "status": "SUCCESS" if ok else "FAILED",
            "detail": detail,
        })

    report_path = BASE / "outputs" / f"reminder_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    fieldnames = ["timestamp_utc", "reminder_id", "contact_id", "recipient_name", "recipient_email", "reminder_title", "due_date", "due_time", "subject", "status", "detail"]
    with open(report_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    logger.info("Batch complete | Total: %d | Success: %d | Failed: %d | Report: %s",
                len(rows_out), sum(x["status"] == "SUCCESS" for x in rows_out), sum(x["status"] == "FAILED" for x in rows_out), report_path.name)


if __name__ == "__main__":
    main()
