"""Every job for a title in a city, with its pay range, to CSV.

    SCRAPEDO_TOKEN=... python examples/pay_ranges.py "Registered Nurse" "Denver, CO" 10
"""

import csv
import statistics
import sys

from careerbuilder_scraper import CareerBuilder

title = sys.argv[1] if len(sys.argv) > 1 else "Registered Nurse"
location = sys.argv[2] if len(sys.argv) > 2 else "Denver, CO"
pages = int(sys.argv[3]) if len(sys.argv) > 3 else 5

cb = CareerBuilder()
jobs = list(cb.search(title, location, pages))
paid = [j for j in jobs if j.salary_min and j.salary_max]

with open("pay_ranges.csv", "w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=["title", "company", "city", "salary_min", "salary_max", "salary_period", "url"],
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(j.to_dict() for j in paid)

hourly = [(j.salary_min + j.salary_max) / 2 for j in paid if j.salary_period == "HOUR" or j.salary_max < 200]
print(f"{len(jobs)} jobs, {len(paid)} with a pay range, {cb.credits_used} credits", file=sys.stderr)
if hourly:
    print(f"median hourly midpoint: ${statistics.median(hourly):.2f}", file=sys.stderr)
