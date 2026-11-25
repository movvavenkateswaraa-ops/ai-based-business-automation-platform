"""Unit tests - run with:  python -m unittest -v"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import automation
from ai_engine import ClaudeEngine, RuleBasedEngine
from config import make_settings
from storage import Store

PROJECT = Path(__file__).parent


class FakeClient:
    """Imitates the Anthropic client: messages.create(...) returns canned text."""

    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        if self.error:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(text=self.reply)])


class RuleEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = RuleBasedEngine()

    def test_angry_billing_ticket_is_high_priority(self):
        r = self.engine.analyze_ticket("Priya", "Charged twice", "I was charged twice. This is unacceptable, refund me immediately.")
        self.assertEqual((r["category"], r["priority"], r["sentiment"]), ("billing", "high", "negative"))
        self.assertIn("sorry", r["reply"])

    def test_happy_feedback_is_low_priority(self):
        r = self.engine.analyze_ticket("Grace", "Feedback", "Love the new export feature. It works perfectly.")
        self.assertEqual((r["priority"], r["sentiment"]), ("low", "positive"))

    def test_not_urgent_is_not_treated_as_urgent(self):
        r = self.engine.analyze_ticket("Lena", "Invoice format", "Can invoices include our VAT number? Not urgent.")
        self.assertEqual((r["category"], r["priority"]), ("billing", "low"))

    def test_unknown_topic_is_general(self):
        r = self.engine.analyze_ticket("Sam", "Hello", "Good morning to the whole team.")
        self.assertEqual(r["category"], "general")

    def test_lead_scoring_tiers(self):
        hot = self.engine.analyze_lead(
            {"company": "Big Co", "email": "a@bigco.com", "employees": "500", "budget": "100000", "source": "referral", "message": "We want to buy, need a demo and pricing this month"}
        )
        cold = self.engine.analyze_lead({"company": "Solo", "email": "x@gmail.com", "employees": "1", "budget": "100", "source": "cold", "message": "info"})
        self.assertEqual(hot["tier"], "hot")
        self.assertEqual(hot["score"], 100)
        self.assertEqual(cold["tier"], "cold")

    def test_bad_numbers_do_not_crash(self):
        r = self.engine.analyze_lead({"company": "X", "employees": "many", "budget": "", "message": ""})
        self.assertEqual(r["tier"], "cold")


class ClaudeEngineTests(unittest.TestCase):
    def test_uses_claude_json_reply(self):
        reply = json.dumps({"category": "shipping", "priority": "medium", "sentiment": "neutral", "summary": "Package delayed.", "reply": "Hi, we are checking. Support Team"})
        engine = ClaudeEngine(FakeClient(reply=f"Here you go:\n{reply}"), "test-model")
        r = engine.analyze_ticket("A", "B", "C")
        self.assertEqual(r["category"], "shipping")
        self.assertEqual(r["engine"], "claude (test-model)")

    def test_invalid_values_are_corrected(self):
        reply = json.dumps({"category": "weird", "priority": "extreme", "sentiment": "meh", "summary": "s", "reply": "r"})
        r = ClaudeEngine(FakeClient(reply=reply), "m").analyze_ticket("A", "B", "C")
        self.assertEqual((r["category"], r["priority"], r["sentiment"]), ("general", "medium", "neutral"))

    def test_lead_score_is_clamped_and_tier_derived(self):
        reply = json.dumps({"score": 250, "summary": "Great fit", "next_action": "Call now"})
        r = ClaudeEngine(FakeClient(reply=reply), "m").analyze_lead({"company": "X"})
        self.assertEqual((r["score"], r["tier"]), (100, "hot"))

    def test_falls_back_when_api_fails(self):
        engine = ClaudeEngine(FakeClient(error=RuntimeError("network down")), "m")
        r = engine.analyze_ticket("A", "Charged twice", "refund me immediately, unacceptable")
        self.assertEqual(r["engine"], "rule-based (fallback)")
        self.assertEqual(r["category"], "billing")

    def test_falls_back_on_garbage_reply(self):
        r = ClaudeEngine(FakeClient(reply="Sorry, I cannot help."), "m").analyze_lead({"company": "X", "employees": "300"})
        self.assertEqual(r["engine"], "rule-based (fallback)")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(PROJECT / "inbox", self.tmp / "inbox")
        self.settings = make_settings(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_run_creates_outputs(self):
        s = automation.run_once(self.settings)
        self.assertEqual((s["new_tickets"], s["new_leads"]), (12, 8))
        self.assertGreater(s["escalations"], 0)
        self.assertTrue((self.tmp / "outbox" / "reply_T-1001.txt").exists())
        self.assertTrue(Path(s["report"]).exists())
        self.assertTrue((self.tmp / "output" / "tickets_triaged.csv").exists())

    def test_second_run_processes_nothing_new(self):
        automation.run_once(self.settings)
        s = automation.run_once(self.settings)
        self.assertEqual((s["new_tickets"], s["new_leads"]), (0, 0))

    def test_new_rows_are_picked_up_later(self):
        automation.run_once(self.settings)
        with (self.tmp / "inbox" / "tickets.csv").open("a", encoding="utf-8") as f:
            f.write('T-2000,New Person,Where is my parcel,"My package tracking shows nothing."\n')
        s = automation.run_once(self.settings)
        self.assertEqual(s["new_tickets"], 1)

    def test_invalid_rows_and_missing_files_are_skipped(self):
        (self.tmp / "inbox" / "tickets.csv").write_text("ticket_id,customer,subject,message\n,Nobody,No id,Has message\nT-1,Someone,No message,\n", encoding="utf-8")
        (self.tmp / "inbox" / "leads.csv").unlink()
        s = automation.run_once(self.settings)
        self.assertEqual((s["new_tickets"], s["new_leads"]), (0, 0))

    def test_unsafe_ticket_id_cannot_escape_outbox(self):
        (self.tmp / "inbox" / "tickets.csv").write_text('ticket_id,customer,subject,message\n../../evil,Eve,Hi,"hello there"\n', encoding="utf-8")
        automation.run_once(self.settings)
        self.assertFalse((self.tmp.parent / "evil.txt").exists())
        self.assertTrue(any(p.name.startswith("reply_") for p in (self.tmp / "outbox").iterdir()))

    def test_audit_log_records_escalation(self):
        automation.run_once(self.settings)
        store = Store(self.settings.db_path)
        events = {e["event"] for e in store.recent_log(200)}
        store.close()
        self.assertIn("ESCALATION", events)
        self.assertIn("HOT_LEAD", events)


if __name__ == "__main__":
    unittest.main()
