"""Command line: careerbuilder-scraper "Data Engineer" --location "Austin, TX" --pages 5 -f csv -o jobs.csv"""

from __future__ import annotations

import argparse
import csv
import json
import sys

from .client import CareerBuilder
from .parser import DETAIL_FIELDS, JOB_FIELDS


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="careerbuilder-scraper",
                                description="Scrape CareerBuilder jobs through the Scrape.do API (token in SCRAPEDO_TOKEN).")
    p.add_argument("title", nargs="?", help='Job title, e.g. "Data Engineer" (optional if --location is given)')
    p.add_argument("-l", "--location", help='City and state ("Austin, TX") or a state ("TX")')
    p.add_argument("--pages", type=int, default=1, help="Result pages, 20 jobs each (0 = all)")
    p.add_argument("--details", action="store_true", help="Open every job page for the full description (1 credit per job)")
    p.add_argument("--job", action="append", default=[], help="A job URL or SEO id to open (repeatable)")
    p.add_argument("-f", "--format", choices=["json", "csv"], default="json")
    p.add_argument("-o", "--output", help="Output file (default: stdout)")
    p.add_argument("--token", help="Scrape.do token (default: SCRAPEDO_TOKEN)")
    args = p.parse_args(argv)
    if not (args.title or args.location or args.job):
        p.error("give a title, --location or --job")

    cb = CareerBuilder(token=args.token)
    fields = DETAIL_FIELDS if (args.details or args.job) else JOB_FIELDS
    rows = [cb.job(u).to_dict() for u in args.job]
    if args.title or args.location:
        for job in cb.search(args.title, args.location, args.pages):
            rows.append(cb.job(job.url).to_dict() if args.details else job.to_dict())
            if len(rows) % 20 == 0:
                print(f"{len(rows)} jobs so far", file=sys.stderr)

    out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        if args.format == "csv":
            writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        else:
            json.dump(rows, out, ensure_ascii=False, indent=2)
            out.write("\n")
    finally:
        if args.output:
            out.close()
    print(f"{len(rows)} jobs, {cb.credits_used} Scrape.do credits", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
