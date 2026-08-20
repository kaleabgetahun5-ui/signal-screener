import argparse
import logging
from datetime import date
from pathlib import Path

from signal_screener import db
from signal_screener import digest as digest_module
from signal_screener import founder_pipeline, pipeline, site, track_record

DEFAULT_DB_DUMP_PATH = "data/signal_screener.sql"


def main():
    parser = argparse.ArgumentParser(prog="signal-screener")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Run the biotech signal pipeline (FDA Breakthrough Therapy + EMA PRIME)"
    )
    run_parser.add_argument(
        "--no-summaries",
        action="store_true",
        help="Skip Claude summarization (useful for testing without an API key)",
    )
    run_parser.add_argument("-v", "--verbose", action="store_true")

    founders_parser = subparsers.add_parser(
        "run-founders", help="Run the founder-led/network-effect Tier 1 (ADR) pipeline"
    )
    founders_parser.add_argument("-v", "--verbose", action="store_true")

    digest_parser = subparsers.add_parser(
        "digest", help="Build the weekly email digest and send it (or print it)"
    )
    digest_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest instead of emailing it (no SMTP config needed)",
    )
    digest_parser.add_argument("-v", "--verbose", action="store_true")

    site_parser = subparsers.add_parser(
        "generate-site", help="Generate the static public HTML page from the current database"
    )
    site_parser.add_argument(
        "--out", default="docs/index.html", help="Output path (default: docs/index.html)"
    )
    site_parser.add_argument("-v", "--verbose", action="store_true")

    dump_parser = subparsers.add_parser(
        "db-dump",
        help="Write the db as a plain-text SQL dump, for committing to git "
        "(the binary db file itself stays gitignored)",
    )
    dump_parser.add_argument(
        "--out", default=DEFAULT_DB_DUMP_PATH, help=f"Output path (default: {DEFAULT_DB_DUMP_PATH})"
    )
    dump_parser.add_argument("-v", "--verbose", action="store_true")

    restore_parser = subparsers.add_parser(
        "db-restore",
        help="Rebuild the db from a plain-text SQL dump written by db-dump "
        "(no-op if the dump doesn't exist yet, e.g. the very first run)",
    )
    restore_parser.add_argument(
        "--in",
        dest="in_path",
        default=DEFAULT_DB_DUMP_PATH,
        help=f"Dump path to restore from (default: {DEFAULT_DB_DUMP_PATH})",
    )
    restore_parser.add_argument("-v", "--verbose", action="store_true")

    note_parser = subparsers.add_parser(
        "add-note",
        help="Attach a personal note to a designation or company entry "
        "(brief section 8 — CLI-only, no web form, no accounts)",
    )
    note_parser.add_argument(
        "entry_id", help="A designation_id (biotech card) or ticker (founder-led card)"
    )
    note_parser.add_argument("note_text", help="The note text")
    note_parser.add_argument("-v", "--verbose", action="store_true")

    check_outcomes_parser = subparsers.add_parser(
        "check-outcomes",
        help="Fill in any due 3/6/12-month price checkpoints in tracked_outcomes "
        "(roadmap step 6 — run this on the same schedule as the rest of the pipeline)",
    )
    check_outcomes_parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "run":
        summary = pipeline.run(generate_summaries=not args.no_summaries)
        print(summary.one_line())
    elif args.command == "run-founders":
        summary = founder_pipeline.run()
        print(f"Processed: {', '.join(summary.processed_tickers)}")
        print(summary.one_line())
    elif args.command == "digest":
        d = digest_module.build_digest()
        if args.dry_run:
            print(f"Subject: {d.subject}\n")
            print(d.body)
        else:
            digest_module.send_digest(d)
            print(f"Sent: {d.subject}")
    elif args.command == "generate-site":
        html_content = site.build_site_html()
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_content, encoding="utf-8")
        print(f"Wrote {out_path} ({len(html_content):,} bytes)")
    elif args.command == "db-dump":
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        db.dump_sql(out_path)
        print(f"Wrote {out_path}")
    elif args.command == "db-restore":
        in_path = Path(args.in_path)
        if in_path.exists():
            db.restore_sql(in_path)
            print(f"Restored db from {in_path}")
        else:
            print(f"No dump at {in_path} — starting with a fresh db.")
    elif args.command == "add-note":
        db.init_db()
        with db.connect() as conn:
            if not db.entry_id_exists(conn, args.entry_id):
                print(
                    f"Warning: {args.entry_id!r} doesn't match any known "
                    "designation_id or ticker — saving the note anyway."
                )
            db.insert_user_note(conn, args.entry_id, args.note_text, date.today().isoformat())
        print(f"Note added to {args.entry_id}.")
    elif args.command == "check-outcomes":
        db.init_db()
        with db.connect() as conn:
            filled = track_record.check_due_outcomes(conn)
        total = sum(filled.values())
        breakdown = ", ".join(f"{n} at {cp}" for cp, n in filled.items())
        print(f"{total} checkpoint(s) recorded: {breakdown}")


if __name__ == "__main__":
    main()
