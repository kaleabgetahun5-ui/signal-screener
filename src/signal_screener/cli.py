import argparse
import logging
from pathlib import Path

from signal_screener import digest as digest_module
from signal_screener import founder_pipeline, pipeline, site


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

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "run":
        ids = pipeline.run(generate_summaries=not args.no_summaries)
        print(f"Processed {len(ids)} designation(s).")
    elif args.command == "run-founders":
        tickers = founder_pipeline.run()
        print(f"Processed {len(tickers)} company(s): {', '.join(tickers)}")
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


if __name__ == "__main__":
    main()
