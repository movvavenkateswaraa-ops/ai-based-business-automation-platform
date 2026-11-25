"""Business workflows: what happens to each ticket and lead.

Support tickets:  AI triage -> route to a team -> set SLA -> draft reply -> escalate if angry + urgent
Sales leads:      AI scoring -> tier (hot/warm/cold) -> next action -> draft follow-up for hot/warm leads

Nothing is sent automatically. Drafts go to the outbox folder for a human to review.
"""

import csv
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

TEAM_BY_CATEGORY = {
    "billing": "Finance",
    "technical": "Technical Support",
    "shipping": "Logistics",
    "account": "Customer Care",
    "sales": "Sales",
    "general": "Customer Care",
}
SLA_HOURS = {"high": 4, "medium": 24, "low": 72}

FOLLOWUP_LINE = {
    "hot": "I would love to set up a short call today to understand your requirements and show you a demo.",
    "warm": "I would be happy to share more details and arrange a demo later this week.",
}


def read_csv(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        log.info("No file at %s - skipping", path)
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_draft(outbox: Path, filename: str, to: str, subject: str, body: str) -> Path:
    """Save an email draft as a text file (never sent automatically)."""
    outbox = Path(outbox)
    outbox.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)  # no path tricks from CSV data
    path = outbox / safe_name
    path.write_text(f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")
    return path


def process_tickets(path, engine, store, outbox) -> list[dict]:
    """Triage every NEW ticket in the CSV. Returns the records created."""
    created = []
    for row in read_csv(path):
        ticket_id = (row.get("ticket_id") or "").strip()
        message = (row.get("message") or "").strip()
        if not ticket_id or not message:
            log.warning("Skipping invalid ticket row: %s", row)
            continue
        if store.has_ticket(ticket_id):
            continue  # already handled in an earlier run

        customer = (row.get("customer") or "Customer").strip()
        subject = (row.get("subject") or "(no subject)").strip()
        ai = engine.analyze_ticket(customer, subject, message)

        team = TEAM_BY_CATEGORY[ai["category"]]
        sla = SLA_HOURS[ai["priority"]]
        escalated = ai["priority"] == "high" and ai["sentiment"] == "negative"

        record = {
            "ticket_id": ticket_id,
            "customer": customer,
            "subject": subject,
            "message": message,
            "category": ai["category"],
            "priority": ai["priority"],
            "sentiment": ai["sentiment"],
            "summary": ai["summary"],
            "reply": ai["reply"],
            "team": team,
            "sla_hours": sla,
            "escalated": int(escalated),
            "engine": ai["engine"],
        }
        store.save_ticket(record)
        write_draft(outbox, f"reply_{ticket_id}.txt", customer, f"Re: {subject}", ai["reply"])
        store.log("TICKET", f"{ticket_id} -> {team} ({ai['priority']} priority, SLA {sla}h)")
        if escalated:
            store.log("ESCALATION", f"{ticket_id} sent to a manager: {subject}")
        created.append(record)
    return created


def process_leads(path, engine, store, outbox) -> list[dict]:
    """Score every NEW lead in the CSV. Returns the records created."""
    created = []
    for row in read_csv(path):
        lead_id = (row.get("lead_id") or "").strip()
        if not lead_id:
            log.warning("Skipping lead row without lead_id: %s", row)
            continue
        if store.has_lead(lead_id):
            continue

        ai = engine.analyze_lead(row)
        record = {
            "lead_id": lead_id,
            "company": (row.get("company") or "").strip(),
            "contact": (row.get("contact") or "").strip(),
            "email": (row.get("email") or "").strip(),
            "employees": (row.get("employees") or "").strip(),
            "budget": (row.get("budget") or "").strip(),
            "source": (row.get("source") or "").strip(),
            "message": (row.get("message") or "").strip(),
            "score": ai["score"],
            "tier": ai["tier"],
            "summary": ai["summary"],
            "next_action": ai["next_action"],
            "engine": ai["engine"],
        }
        store.save_lead(record)
        store.log("LEAD", f"{lead_id} {record['company']} scored {ai['score']} ({ai['tier']})")

        if ai["tier"] in FOLLOWUP_LINE:
            body = (
                f"Hi {record['contact'] or 'there'},\n\n"
                f"Thank you for your interest. {FOLLOWUP_LINE[ai['tier']]}\n\n"
                "Best regards,\nSales Team"
            )
            write_draft(outbox, f"followup_{lead_id}.txt", record["email"], "Following up on your enquiry", body)
        if ai["tier"] == "hot":
            store.log("HOT_LEAD", f"{lead_id} {record['company']}: {ai['next_action']}")
        created.append(record)
    return created
