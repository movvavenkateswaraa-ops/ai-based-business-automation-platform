"""Reports: a Markdown summary plus CSV exports of everything processed."""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def _md_table(headers, rows) -> str:
    if not rows:
        return "_None_\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c).replace("|", "/") for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _counts(rows, key, order) -> str:
    counter = Counter(r[key] for r in rows)
    return _md_table([key.title(), "Count"], [(k, counter[k]) for k in order if counter[k]])


def build_report(store, engine_name: str) -> str:
    tickets, leads = store.all_tickets(), store.all_leads()
    escalated = [t for t in tickets if t["escalated"]]
    hot = [lead for lead in leads if lead["tier"] == "hot"]

    out = [
        "# Business Automation Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"AI engine: **{engine_name}**",
        "",
        "## Customer support",
        f"- Tickets processed: **{len(tickets)}**",
        f"- Escalated to a manager: **{len(escalated)}**",
        "",
        "### By category",
        _counts(tickets, "category", ["billing", "technical", "shipping", "account", "sales", "general"]),
        "### By priority",
        _counts(tickets, "priority", ["high", "medium", "low"]),
        "### By sentiment",
        _counts(tickets, "sentiment", ["negative", "neutral", "positive"]),
        "### Escalations",
        _md_table(
            ["Ticket", "Customer", "Subject", "Team", "SLA (h)"],
            [(t["ticket_id"], t["customer"], t["subject"], t["team"], t["sla_hours"]) for t in escalated],
        ),
        "## Sales leads",
        f"- Leads scored: **{len(leads)}**",
        f"- Hot leads: **{len(hot)}**",
        "",
        "### By tier",
        _counts(leads, "tier", ["hot", "warm", "cold"]),
        "### Top leads",
        _md_table(
            ["Lead", "Company", "Score", "Tier", "Next action"],
            [(lead["lead_id"], lead["company"], lead["score"], lead["tier"], lead["next_action"]) for lead in leads[:5]],
        ),
        "## Recent automation log",
        _md_table(["Time", "Event", "Detail"], [(e["at"], e["event"], e["detail"]) for e in store.recent_log(10)]),
    ]
    return "\n".join(out)


def export_csvs(store, out_dir: Path) -> None:
    for name, rows in (("tickets_triaged.csv", store.all_tickets()), ("leads_scored.csv", store.all_leads())):
        if not rows:
            continue
        with (out_dir / name).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


def write_report(store, out_dir: Path, engine_name: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"report_{datetime.now().strftime('%Y-%m-%d')}.md"
    path.write_text(build_report(store, engine_name), encoding="utf-8")
    export_csvs(store, out_dir)
    return path
