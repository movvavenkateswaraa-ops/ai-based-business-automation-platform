"""AI-Based Business Automation Platform - command line.

    python main.py run                 process everything new in inbox/ once
    python main.py watch --interval 30 keep checking inbox/ every 30 seconds
    python main.py reset               delete the database, outbox and output
"""

import argparse
import logging
import shutil
import time

from automation import run_once
from config import load_settings

log = logging.getLogger("main")


def print_summary(s: dict) -> None:
    print(
        f"[{s['engine']}] new tickets: {s['new_tickets']} (escalated {s['escalations']}), "
        f"new leads: {s['new_leads']} (hot {s['hot_leads']})"
    )
    print(f"Report: {s['report']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-Based Business Automation Platform")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="process new items once")
    watch = sub.add_parser("watch", help="process new items repeatedly")
    watch.add_argument("--interval", type=int, default=30, help="seconds between checks")
    sub.add_parser("reset", help="delete database, outbox and output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    settings = load_settings()

    if args.command == "run":
        print_summary(run_once(settings))
    elif args.command == "watch":
        print(f"Watching {settings.inbox} every {args.interval}s - press Ctrl+C to stop")
        try:
            while True:
                summary = run_once(settings)
                if summary["new_tickets"] or summary["new_leads"]:
                    print_summary(summary)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("Stopped.")
    elif args.command == "reset":
        settings.db_path.unlink(missing_ok=True)
        shutil.rmtree(settings.outbox, ignore_errors=True)
        shutil.rmtree(settings.output, ignore_errors=True)
        print("Reset done (inbox files were left untouched).")


if __name__ == "__main__":
    main()
