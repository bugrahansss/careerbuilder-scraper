# CareerBuilder Scraper

[![PyPI](https://img.shields.io/pypi/v/careerbuilder-scraper)](https://pypi.org/project/careerbuilder-scraper/)
[![Python](https://img.shields.io/pypi/pyversions/careerbuilder-scraper)](https://pypi.org/project/careerbuilder-scraper/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Scrape [CareerBuilder](https://www.careerbuilder.com) job listings into structured data. Search by **job title, city or state** and get every job's **title, company, city, state, ZIP, coordinates, pay range and pay period, work mode (on-site, hybrid, remote), employment type, posting date, apply type and short description**. Open a job for the **full description**, education requirement, normalized title and expiry date. JSON or CSV.

```bash
pip install careerbuilder-scraper
export SCRAPEDO_TOKEN=your_token
careerbuilder-scraper "Registered Nurse" -l "Denver, CO" --pages 10 -f csv -o denver_rn.csv   # 200 jobs, 10 credits
careerbuilder-scraper "Data Engineer" -l "TX" --pages 3 --details -o tx_data.json            # + full descriptions
careerbuilder-scraper -l "Austin, TX" -f csv -o austin.csv                                   # every job in a city
```

## Why plain requests fail

```python
import requests

r = requests.get("https://www.careerbuilder.com/jobs-registered-nurse-in-denver,co")
print(r.status_code)   # 403
print(r.text[:120])    # ... Please enable JS and disable any ad blocker ...
```

careerbuilder.com is protected by DataDome, which answers a script with `403` and a challenge from captcha-delivery.com. This package sends each request through [Scrape.do](https://scrape.do/?utm_source=github&utm_medium=readme&utm_campaign=careerbuilder-scraper), which returns the real page. A plain request is enough, no extra parameters: **1 credit per page**.

## Where the data is

CareerBuilder is a Next.js site, so every page carries its data in `<script id="__NEXT_DATA__">`:

* **Search pages**: `/jobs-<title>-in-<city>,<state>`, `/jobs-in-<city>,<state>`, `/jobs-in-<state>` or `/jobs-<title>`, plus `?page=N`. `props.pageProps.jobResultsData.jobResults` holds 20 jobs per page (title, company, location with coordinates, pay range, employment type, work mode, apply type, short description) and `estimatedTotalSize` the total.
* **Job pages**: `/job-details/<seo-id>`. `props.pageProps.jobViewResultsData` holds the full posting: HTML description, education, normalized title, expiry.

These are CareerBuilder's popular search pages. Common titles and every US city and state have one; a title CareerBuilder has no page for returns `404`.

In a live test, "Registered Nurse" in Denver, CO showed 9,606 jobs. The first 10 pages gave **200 jobs for 10 credits** from 47 employers in 16 cities; 191 were posted in November. 43 listed a pay range, but 41 of those had no pay period: most were hourly ranges, with a median midpoint of $52.50 an hour. Keep `salary_period` empty when CareerBuilder leaves it empty.

## Python

```python
from careerbuilder_scraper import CareerBuilder

cb = CareerBuilder(token="YOUR_SCRAPEDO_TOKEN")   # or set SCRAPEDO_TOKEN

for job in cb.search("Registered Nurse", "Denver, CO", pages=2):
    print(job.title, job.company, job.city, job.salary_min, job.salary_max, job.salary_period)

detail = cb.job(job.url)
print(detail.education, detail.description_text[:300])
print(cb.credits_used)
```

`examples/pay_ranges.py` writes every job with a pay range for a title and city to CSV.

## Fields

**Job:** `id`, `title`, `company`, `city`, `state`, `postal_code`, `country`, `latitude`, `longitude`, `work_mode` (`ONSITE`, `HYBRID`, `REMOTE`), `employment_types`, `salary_min`, `salary_max`, `salary_currency`, `salary_period` (`HOUR`, `WEEK`, `YEAR`, ... or empty), `date_posted`, `short_description`, `apply_type` (`INTEGRATED` = apply on CareerBuilder, `OFFSITE` = employer site), `promoted`, `source`, `url`.

**Job detail:** everything above plus `description_text`, `description_html`, `education`, `normalized_title`, `valid_through`, `company_reference`.

Recruiter email addresses that some postings carry are deliberately not exported.

## Use it responsibly

Job postings are public business data. Respect CareerBuilder's terms, keep request rates reasonable, and don't republish full descriptions as your own job board. This is not legal advice.

## Tests

```bash
pip install pytest
PYTHONPATH=src pytest
```

The fixtures are fictional ("Example Corp", "Exemple & Co", example.com).

## License

MIT
