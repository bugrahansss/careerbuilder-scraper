"""Parsers for CareerBuilder's server-rendered job pages.

CareerBuilder is a Next.js site. Every page carries its data in ``<script id="__NEXT_DATA__">``:

* Search pages (``/jobs-data-engineer-in-austin,tx``, ``/jobs-in-austin,tx``, ``/jobs-data-engineer``,
  ``?page=N``) hold ``props.pageProps.jobResultsData``: 20 jobs per page plus ``estimatedTotalSize``.
* Job pages (``/job-details/<seo-id>``) hold ``props.pageProps.jobViewResultsData`` with the full posting.

These are CareerBuilder's popular search pages: a job title, a city or state, or both. A title CareerBuilder
has no page for returns 404.
"""

from __future__ import annotations

import html as htmllib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

BASE = "https://www.careerbuilder.com"
PAGE_SIZE = 20
_NEXT = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
PERIODS = {"hour": "HOUR", "per hour": "HOUR", "year": "YEAR", "per year": "YEAR", "annual": "YEAR",
           "hourly": "HOUR", "annually": "YEAR", "yearly": "YEAR", "monthly": "MONTH", "weekly": "WEEK", "daily": "DAY",
           "month": "MONTH", "per month": "MONTH", "week": "WEEK", "per week": "WEEK", "day": "DAY", "per day": "DAY"}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", (value or "").lower().replace("&", "and"))
    return value.strip("-")


def location_slug(location: str) -> str:
    """'Austin, TX' -> 'austin,tx'; 'TX' -> 'tx'; 'New York, NY' -> 'new-york,ny'."""
    parts = [slugify(p) for p in (location or "").split(",") if p.strip()]
    return ",".join(parts)


def search_url(title: Optional[str] = None, location: Optional[str] = None, page: int = 1) -> str:
    if not title and not location:
        raise ValueError("Give a job title, a location, or both.")
    path = "/jobs"
    if title:
        path += "-" + slugify(title)
    if location:
        path += "-in-" + location_slug(location)
    return BASE + path + (f"?page={page}" if page and page > 1 else "")


def job_url(value: str) -> str:
    v = (value or "").strip()
    if v.startswith("http"):
        return v.split("?")[0]
    if v.startswith("/job-details/"):
        return BASE + v
    return f"{BASE}/job-details/{v}"


def next_data(html: str) -> Optional[Dict[str, Any]]:
    m = _NEXT.search(html or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))["props"]["pageProps"]
    except (ValueError, KeyError, TypeError):
        return None


def strip_html(fragment: str) -> str:
    text = re.sub(r"<(br|/p|/li|/h\d|/div)[^>]*>", "\n", fragment or "", flags=re.I)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
    text = htmllib.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _period(unit: Any) -> str:
    u = str(unit or "").strip().lower()
    return PERIODS.get(u, u.upper())


# ---- data ----------------------------------------------------------------------

@dataclass
class Job:
    id: str
    title: str
    company: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    work_mode: str
    employment_types: List[str]
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_currency: str
    salary_period: str
    date_posted: str
    short_description: str
    apply_type: str
    promoted: bool
    source: str
    url: str

    def to_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        row["employment_types"] = ", ".join(self.employment_types)
        return row


@dataclass
class SearchPage:
    jobs: List[Job]
    total: Optional[int]
    offset: int
    query: str
    location: str

    @property
    def pages(self) -> int:
        return -(-(self.total or 0) // PAGE_SIZE) if self.total else 1


@dataclass
class JobDetail(Job):
    description_text: str = ""
    description_html: str = ""
    education: str = ""
    normalized_title: str = ""
    valid_through: str = ""
    company_reference: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        row = super().to_dict()
        row.pop("extra", None)
        return row


JOB_FIELDS = list(Job.__dataclass_fields__)
DETAIL_FIELDS = [f for f in JobDetail.__dataclass_fields__ if f not in ("extra",)]


def _location(posting: Dict, enrich: Dict) -> Dict[str, Any]:
    loc = (posting.get("jobLocation") or [{}])[0] or {}
    addr = loc.get("address") or {}
    geo = {}
    for n in enrich.get("normalizedJobLocations") or []:
        pa = n.get("postalAddress") or {}
        geo = pa.get("geo") or {}
        if not addr:
            addr = pa.get("address") or {}
        break

    def num(v):
        try:
            return round(float(v), 6)
        except (TypeError, ValueError):
            return None
    return {"city": addr.get("addressLocality") or "", "state": addr.get("addressRegion") or "",
            "postal_code": addr.get("postalCode") or "", "country": addr.get("addressCountry") or "",
            "latitude": num(geo.get("latitude")), "longitude": num(geo.get("longitude"))}


def _salary(posting: Dict, normalized: Dict, enrich: Dict) -> Dict[str, Any]:
    sal = posting.get("baseSalary") or {}
    if not (sal.get("value") or {}).get("minValue") and not (sal.get("value") or {}).get("maxValue"):
        sal = (normalized or {}).get("baseSalary") or sal
    val = sal.get("value") or {}
    unit = val.get("unitText") or ((enrich.get("normalizedSalary") or {}).get("salaryBaseType") or {}).get("name") or ""
    if str(unit).upper() == "UNKNOWN":
        unit = ""
    return {"salary_min": val.get("minValue"), "salary_max": val.get("maxValue"),
            "salary_currency": sal.get("currency") or "", "salary_period": _period(unit) if (val.get("minValue") or val.get("maxValue")) else ""}


def _work_mode(item: Dict) -> str:
    res = ((item.get("policyDecisions") or {}).get("jobLocationTypeDecision") or {}).get("result")
    if res:
        return str(res)
    jlt = ((item.get("enrichments") or {}).get("jobLocationType") or {}).get("name")
    return "" if not jlt or jlt == "UNKNOWN" else str(jlt)


def _job(item: Dict[str, Any], cls=Job, **extra) -> Job:
    posting = item.get("jobPosting") or {}
    enrich = item.get("enrichments") or {}
    url = item.get("canonicalUrl") or posting.get("url") or ""
    if url.startswith("/"):
        url = BASE + url
    return cls(
        id=str(item.get("jobId") or ""),
        title=htmllib.unescape(posting.get("title") or ""),
        company=htmllib.unescape((posting.get("hiringOrganization") or {}).get("name") or ""),
        **_location(posting, enrich),
        work_mode=_work_mode(item),
        employment_types=[str(e) for e in (posting.get("employmentType") or [])],
        **_salary(posting, item.get("normalizedJobPosting") or {}, enrich),
        source=htmllib.unescape(str((item.get("provider") or {}).get("name") or "")),
        date_posted=(posting.get("datePosted") or "")[:10],
        short_description=((enrich.get("processedDescriptions") or {}).get("shortDescription") or "").strip(),
        apply_type=str((item.get("apply") or {}).get("applyType") or ""),
        promoted=bool(item.get("promoted")),
        url=url,
        **extra,
    )


# ---- pages ---------------------------------------------------------------------

def parse_search(html: str) -> Optional[SearchPage]:
    pp = next_data(html)
    if not pp or not pp.get("jobResultsData"):
        return None
    data = pp["jobResultsData"]
    req = data.get("jobRequest") or {}
    q = req.get("jobQuery") or {}
    loc = ((q.get("locations") or [{}])[0] or {}).get("address") or ""
    jobs, seen = [], set()
    for item in data.get("jobResults") or []:
        job = _job(item)
        if job.id and job.id not in seen:
            seen.add(job.id)
            jobs.append(job)
    total = data.get("estimatedTotalSize")
    return SearchPage(jobs=jobs, total=int(total) if isinstance(total, (int, float)) else None,
                      offset=int(req.get("offset") or 0), query=q.get("query") or "", location=loc)


def parse_job(html: str) -> Optional[JobDetail]:
    pp = next_data(html)
    item = (pp or {}).get("jobViewResultsData") or {}
    if not item.get("jobPosting"):
        return None
    posting = item["jobPosting"]
    enrich = item.get("enrichments") or {}
    desc = posting.get("description") or ""
    titles = enrich.get("normalizedTitles") or [{}]
    ident = posting.get("identifier") or {}
    return _job(
        item, JobDetail,
        description_text=strip_html(desc),
        description_html=desc,
        education=posting.get("educationRequirements") or "",
        normalized_title=(titles[0] or {}).get("title") or "",
        valid_through=(enrich.get("googleSyntheticValidThrough") or "")[:10],
        company_reference=str(ident.get("value") or ""),
    )
