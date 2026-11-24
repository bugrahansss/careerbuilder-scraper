from pathlib import Path

import pytest

from careerbuilder_scraper import CareerBuilder, ScrapeError, job_url, location_slug, parse_job, parse_search, search_url

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_urls():
    assert search_url("Data Engineer", "Austin, TX") == "https://www.careerbuilder.com/jobs-data-engineer-in-austin,tx"
    assert search_url("Data Engineer", "Austin, TX", 3).endswith("/jobs-data-engineer-in-austin,tx?page=3")
    assert search_url(None, "New York, NY") == "https://www.careerbuilder.com/jobs-in-new-york,ny"
    assert search_url("Registered Nurse") == "https://www.careerbuilder.com/jobs-registered-nurse"
    assert search_url(location="TX") == "https://www.careerbuilder.com/jobs-in-tx"
    assert location_slug(" Saint Louis , MO ") == "saint-louis,mo"
    assert job_url("data-engineer-austin-tx--abc") == "https://www.careerbuilder.com/job-details/data-engineer-austin-tx--abc"
    assert job_url("https://www.careerbuilder.com/job-details/x--1?ipath=y") == "https://www.careerbuilder.com/job-details/x--1"
    with pytest.raises(ValueError):
        search_url()


def test_search_page():
    page = parse_search(load("search.html"))
    assert page.total == 47 and page.pages == 3 and page.offset == 20
    assert page.query == "Data Engineer" and page.location == "Austin, TX"
    assert [j.id[-1] for j in page.jobs] == ["1", "2", "3"]
    a, b, c = page.jobs
    assert a.title == "Data Engineer" and a.company == "Example Corp"
    assert (a.city, a.state, a.postal_code, a.country) == ("Austin", "TX", "78701", "US")
    assert a.latitude == 30.1 and a.longitude == -97.7
    assert (a.salary_min, a.salary_max, a.salary_currency, a.salary_period) == (120000, 150000, "USD", "YEAR")
    assert a.employment_types == ["FULL_TIME"] and a.date_posted == "2026-11-11"
    assert a.url.endswith("--00000000-0000-0000-0000-000000000001")
    assert b.company == "Exemple & Co" and b.salary_period == "HOUR" and b.work_mode == "HYBRID" and b.source == "Example Feed"
    assert b.to_dict()["employment_types"] == "CONTRACTOR, TEMPORARY"
    assert c.salary_min is None and c.salary_period == "" and c.work_mode == "REMOTE" and c.promoted and c.apply_type == "OFFSITE"


def test_job_detail():
    job = parse_job(load("job.html"))
    assert job.title == "Data Engineer" and job.company == "Example Corp"
    assert "Build pipelines for Example Corp's fictional data platform." in job.description_text
    assert "- Python" in job.description_text and "<ul>" in job.description_html
    assert job.education == "Bachelor's Degree" and job.normalized_title == "Data Engineer"
    assert job.valid_through == "2026-12-11" and job.company_reference == "REQ-0001"
    assert job.url.startswith("https://www.careerbuilder.com/job-details/")
    row = job.to_dict()
    assert "jane.doe@example.com" not in str(row)  # recruiter emails are never exported
    assert "extra" not in row


def test_missing():
    assert parse_search("<html></html>") is None
    assert parse_job(load("search.html")) is None
    assert parse_job("<html></html>") is None


class FakeResponse:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params["url"])
        r = self.responses(params["url"], len(self.calls))
        return FakeResponse(*r) if isinstance(r, tuple) else FakeResponse(r)


def test_client_search_pages_and_dedupe(monkeypatch):
    monkeypatch.setattr("careerbuilder_scraper.client.time.sleep", lambda s: None)
    s = FakeSession(lambda url, n: load("search.html"))
    cb = CareerBuilder(token="t", session=s)
    jobs = list(cb.search("Data Engineer", "Austin, TX", pages=3))
    assert len(jobs) == 3  # same jobs on page 2 stop the loop
    assert s.calls == ["https://www.careerbuilder.com/jobs-data-engineer-in-austin,tx",
                       "https://www.careerbuilder.com/jobs-data-engineer-in-austin,tx?page=2"]
    assert cb.credits_used == 2


def test_client_blocked_then_ok(monkeypatch):
    monkeypatch.setattr("careerbuilder_scraper.client.time.sleep", lambda s: None)
    s = FakeSession(lambda url, n: load("blocked.html") if n == 1 else load("job.html"))
    cb = CareerBuilder(token="t", session=s)
    assert cb.job("data-engineer--1").company == "Example Corp"
    assert len(s.calls) == 2


def test_client_404(monkeypatch):
    monkeypatch.setattr("careerbuilder_scraper.client.time.sleep", lambda s: None)
    cb = CareerBuilder(token="t", session=FakeSession(lambda url, n: ("Page Not Found", 404)))
    with pytest.raises(ScrapeError) as err:
        list(cb.search("Unknown Title"))
    assert err.value.status_code == 404


def test_token_required(monkeypatch):
    monkeypatch.delenv("SCRAPEDO_TOKEN", raising=False)
    with pytest.raises(ValueError):
        CareerBuilder()
