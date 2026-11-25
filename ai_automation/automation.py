"""One automation cycle: read inbox -> AI -> actions -> report."""

import logging

import reporting
import workflows
from ai_engine import get_engine
from storage import Store

log = logging.getLogger(__name__)


def run_once(settings, engine=None, store=None) -> dict:
    """Process everything new in the inbox and refresh the report.

    Returns a small summary dict. Pass `engine` / `store` to override
    (the tests do this); otherwise they are created from the settings.
    """
    engine = engine or get_engine(settings)
    owns_store = store is None
    store = store or Store(settings.db_path)
    try:
        tickets = workflows.process_tickets(settings.inbox / "tickets.csv", engine, store, settings.outbox)
        leads = workflows.process_leads(settings.inbox / "leads.csv", engine, store, settings.outbox)

        summary = {
            "engine": engine.name,
            "new_tickets": len(tickets),
            "new_leads": len(leads),
            "escalations": sum(t["escalated"] for t in tickets),
            "hot_leads": sum(1 for lead in leads if lead["tier"] == "hot"),
        }
        store.log("RUN", f"{summary['new_tickets']} tickets, {summary['new_leads']} leads processed with {engine.name}")
        summary["report"] = str(reporting.write_report(store, settings.output, engine.name))
        return summary
    finally:
        if owns_store:
            store.close()
