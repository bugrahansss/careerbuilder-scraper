"""Scrape CareerBuilder job listings and job pages with Python."""

from .client import CareerBuilder, ScrapeError
from .parser import (
    DETAIL_FIELDS,
    JOB_FIELDS,
    Job,
    JobDetail,
    SearchPage,
    job_url,
    location_slug,
    parse_job,
    parse_search,
    search_url,
    slugify,
)

__version__ = "0.1.0"
__all__ = [
    "CareerBuilder", "ScrapeError", "Job", "JobDetail", "SearchPage", "parse_search", "parse_job",
    "search_url", "job_url", "slugify", "location_slug", "JOB_FIELDS", "DETAIL_FIELDS",
]
