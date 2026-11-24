import argparse
from pathlib import Path

from src.config import get_settings
from src.reporter import setup_logger
from src.scheduler import run_batch_once, start_scheduler_loop


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Email Automation & Reminder System (CSV + SMTP + Dry-Run Support)"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate sending emails without connecting to an SMTP server.",
    )
    mode_group.add_argument(
        "--send",
        action="store_true",
        help="Send real emails using configured SMTP credentials in .env.",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run continuously on a recurring interval instead of a single run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    logger = setup_logger(base_dir / "logs")

    dry_run_override = True if args.dry_run else (False if args.send else None)
    settings = get_settings(dry_run_override=dry_run_override)

    logger.info(
        "Initialized | Mode: %s | Schedule: %s | SMTP Host: %s:%s",
        "DRY-RUN" if settings.dry_run else "LIVE-SMTP",
        "CONTINUOUS" if args.schedule else "SINGLE-RUN",
        settings.smtp_host,
        settings.smtp_port,
    )

    if args.schedule:
        start_scheduler_loop(base_dir, settings, logger)
    else:
        run_batch_once(base_dir, settings, logger)


if __name__ == "__main__":
    main()
