"""Settings for the AI-Based Business Automation Platform.

Everything has a sensible default, so the platform runs with no setup.
If ANTHROPIC_API_KEY is set, Claude is used as the AI engine; otherwise a
built-in rule-based engine is used (works offline, no cost).
"""

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

DEFAULT_MODEL = "claude-sonnet-5-5"


@dataclass(frozen=True)
class Settings:
    inbox: Path  # where new tickets.csv / leads.csv arrive
    outbox: Path  # drafted emails are written here (for human review)
    output: Path  # reports and CSV exports
    db_path: Path  # SQLite database
    api_key: str | None  # Anthropic API key (optional)
    model: str  # Claude model name


def make_settings(base: Path, api_key: str | None = None, model: str = DEFAULT_MODEL) -> Settings:
    base = Path(base)
    return Settings(
        inbox=base / "inbox",
        outbox=base / "outbox",
        output=base / "output",
        db_path=base / "automation.db",
        api_key=api_key,
        model=model,
    )


def load_settings() -> Settings:
    return make_settings(
        base=Path(os.getenv("BASE_DIR", ".")),
        api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        model=os.getenv("CLAUDE_MODEL", DEFAULT_MODEL),
    )
