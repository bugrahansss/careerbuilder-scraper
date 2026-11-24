"""Fetch CareerBuilder pages through the Scrape.do API.

careerbuilder.com sits behind DataDome: a plain ``requests.get`` from a script gets ``403`` and a
"Please enable JS and disable any ad blocker" page from captcha-delivery.com. A plain Scrape.do request
(no extra parameters) returns the real server-rendered page. Each page costs 1 Scrape.do credit.
"""

from __future__ import annotations

import os
import time
from typing import Iterator, List, Optional

import requests

from .parser import Job, JobDetail, SearchPage, job_url, parse_job, parse_search, search_url

API_URL = "https://api.scrape.do/"
TOKEN_ENV = "SCRAPEDO_TOKEN"
BLOCK_MARKERS = ("Please enable JS and disable any ad blocker", "captcha-delivery.com")


class ScrapeError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class CareerBuilder:
    """Search CareerBuilder jobs by title and location, and open job pages.

    >>> cb = CareerBuilder(token="YOUR_SCRAPEDO_TOKEN")
    >>> for job in cb.search("Data Engineer", "Austin, TX", pages=2):
    ...     print(job.title, job.company, job.salary_min, job.salary_max)
    >>> detail = cb.job(job.url)
    """

    def __init__(self, token: Optional[str] = None, timeout: float = 90.0, retries: int = 2,
                 session: Optional[requests.Session] = None):
        self.token = token or os.environ.get(TOKEN_ENV, "")
        if not self.token:
            raise ValueError(f"A Scrape.do API token is required. Pass token=... or set {TOKEN_ENV}.")
        self.timeout = timeout
        self.retries = max(0, retries)
        self.session = session or requests.Session()
        self.requests_made = 0

    def fetch(self, url: str) -> str:
        params = {"token": self.token, "url": url}
        last: Optional[ScrapeError] = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(API_URL, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                last = ScrapeError(f"Request failed: {exc}")
            else:
                self.requests_made += 1
                if response.status_code == 200:
                    if not any(m in response.text for m in BLOCK_MARKERS):
                        return response.text
                    last = ScrapeError(f"Blocked page for {url} (DataDome)", 200)
                else:
                    last = ScrapeError(f"Request for {url} failed with status {response.status_code}",
                                       response.status_code)
                    if response.status_code in (400, 401, 404, 410):
                        break
            if attempt < self.retries:
                time.sleep(2 * (attempt + 1))
        assert last is not None
        raise last

    def search_page(self, title: Optional[str] = None, location: Optional[str] = None, page: int = 1) -> SearchPage:
        """One page of results (20 jobs). Raises ScrapeError(404) when CareerBuilder has no page for the title."""
        url = search_url(title, location, page)
        result = parse_search(self.fetch(url))
        if result is None:
            raise ScrapeError(f"No job results on {url}")
        return result

    def search(self, title: Optional[str] = None, location: Optional[str] = None, pages: int = 1) -> Iterator[Job]:
        """Jobs for a title, a location (``"Austin, TX"`` or ``"TX"``), or both. ``pages=0`` follows every page."""
        seen = set()
        page, last_page = 1, None
        while True:
            if (pages and page > pages) or (last_page is not None and page > last_page):
                break
            result = self.search_page(title, location, page)
            last_page = result.pages
            fresh = [j for j in result.jobs if j.id not in seen]
            if not fresh:
                break
            for job in fresh:
                seen.add(job.id)
                yield job
            page += 1

    def job(self, url_or_id: str) -> JobDetail:
        url = job_url(url_or_id)
        detail = parse_job(self.fetch(url))
        if detail is None:
            raise ScrapeError(f"No job data on {url}")
        return detail

    def search_with_details(self, title: Optional[str] = None, location: Optional[str] = None,
                            pages: int = 1) -> List[JobDetail]:
        return [self.job(j.url) for j in self.search(title, location, pages)]

    @property
    def credits_used(self) -> int:
        return self.requests_made
