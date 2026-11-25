# AI-Based Business Automation Platform

A simple base project that uses AI to automate two everyday business jobs:

1. **Customer support triage** - read incoming tickets, work out the category, priority and
   mood, route each ticket to the right team, set a response deadline (SLA), draft a reply,
   and escalate angry + urgent cases to a manager.
2. **Sales lead qualification** - score each lead from 0-100, label it hot / warm / cold,
   suggest the next action, and draft a follow-up email for the best leads.

Nothing is sent automatically. Drafts are saved in `outbox/` so a person can review them.

```
 inbox/tickets.csv ─┐                    ┌─> outbox/   (email drafts)
 inbox/leads.csv   ─┴─> AI engine ──> workflows ─> automation.db (history + audit log)
                                             └─> output/   (Markdown report + CSV exports)
```

## Two AI engines, same interface

| Engine | When | Notes |
|--------|------|-------|
| **Rule-based** (default) | no API key set | free, instant, works offline |
| **Claude** | `ANTHROPIC_API_KEY` is set | smarter classification and tailored replies. If the API fails or returns bad JSON, that item automatically falls back to the rules, so the automation never stops |

Ticket and lead text is treated as untrusted data in the Claude prompts, and the model's answers
are validated before use (unknown categories are corrected, scores are clamped to 0-100).

## Project structure

```
ai_automation/
├── main.py              # CLI: run / watch / reset
├── automation.py        # one automation cycle
├── ai_engine.py         # RuleBasedEngine + ClaudeEngine
├── workflows.py         # what happens to each ticket / lead
├── storage.py           # SQLite: results + audit log
├── reporting.py         # Markdown report + CSV exports
├── config.py            # settings
├── inbox/               # sample tickets.csv and leads.csv
└── test_platform.py     # unit tests
```

## How to run

```bash
python main.py run          # process everything new in inbox/ once
python main.py run          # run again - nothing is processed twice
python main.py watch --interval 30   # keep checking for new rows
python main.py reset        # start over
python -m unittest -v       # run the tests
```

Then look at:
- `output/report_<date>.md` - the summary report
- `output/tickets_triaged.csv`, `output/leads_scored.csv` - full results
- `outbox/` - drafted replies and follow-ups

To add work, append rows to `inbox/tickets.csv` or `inbox/leads.csv` and run again.

### Using Claude

```bash
pip install -r requirements.txt
cp .env.example .env      # then paste your key after ANTHROPIC_API_KEY=
python main.py reset
python main.py run
```

The report header shows which engine did the work.

## Ideas for taking it further

- Connect real email / Slack / CRM instead of CSV files and the outbox folder.
- A web dashboard (Flask or Streamlit) on top of `automation.db`.
- More workflows: invoice data extraction, meeting-notes summaries, resume screening.
- A human approval step before drafts are sent.
