from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import html
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _strip_markup(value: str) -> str:
    """Bo the JATS/HTML (vd `<jats:p>`) va chuan hoa khoang trang."""
    return normalize_whitespace(html.unescape(_TAG_RE.sub(" ", value or "")))


def _first_text(value) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return _strip_markup(str(value or ""))


def _date_from_parts(field: dict | None) -> str:
    """Chuyen `{"date-parts": [[2026, 5, 20]]}` thanh `2026-05-20`."""
    if not field:
        return ""
    parts = (field.get("date-parts") or [[]])[0]
    if not parts or parts[0] is None:
        return ""
    year, month, day = (list(parts) + [1, 1])[:3]
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _author_name(author: dict) -> str:
    name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
    return normalize_whitespace(name or author.get("name", ""))


def _pdf_url(item: dict, fallback: str) -> str:
    for link in item.get("link") or []:
        if "pdf" in str(link.get("content-type", "")).lower() and link.get("URL"):
            return link["URL"]
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord, bo record thieu DOI/title/abstract/ngay."""
    items = (payload.get("message") or {}).get("items") or []
    records: list[PaperRecord] = []
    seen: set[str] = set()

    for item in items:
        paper_id = normalize_whitespace(str(item.get("DOI") or "")).lower()
        title = _first_text(item.get("title"))
        summary = _strip_markup(item.get("abstract") or "")
        published = (
            _date_from_parts(item.get("published"))
            or _date_from_parts(item.get("published-print"))
            or _date_from_parts(item.get("published-online"))
            or _date_from_parts(item.get("issued"))
        )
        if not paper_id or not title or not summary or not published or paper_id in seen:
            continue
        seen.add(paper_id)

        authors = [name for name in (_author_name(a) for a in item.get("author") or []) if name]
        categories = [normalize_whitespace(s) for s in item.get("subject") or [] if normalize_whitespace(s)]
        updated_raw = (item.get("updated") or item.get("created") or {}).get("date-time", "")
        abs_url = item.get("URL") or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated_raw[:10] or published,
                abs_url=abs_url,
                pdf_url=_pdf_url(item, abs_url),
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def _request_crossref(settings: Settings, max_attempts: int = 3) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": "DOI,title,abstract,author,subject,published,published-print,published-online,issued,created,updated,URL,link",
    }
    headers = {"User-Agent": "day10-data-observability-lab/0.1 (mailto:lab@example.com)"}
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(CROSSREF_WORKS_URL, params=params, headers=headers, timeout=30)
            if response.status_code in RETRYABLE_STATUS:
                raise requests.HTTPError(f"Crossref returned {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < max_attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Crossref API failed after {max_attempts} attempts: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Lay payload Crossref (API hoac snapshot offline), luu raw artifacts va tra ve records.

    - Mac dinh dung snapshot `data/raw/crossref_response.json` neu da co (offline-first,
      tranh Rate Limit). Dat `REFRESH_SOURCE=1` de goi API that.
    - Neu API loi (429/503/mat mang) thi fallback ve snapshot.
    """
    raw_path = settings.paths.raw_api_response
    payload: dict | None = None

    if settings.refresh_source or not raw_path.exists():
        try:
            payload = _request_crossref(settings)
            records = parse_crossref_payload(payload)
            if not records:
                raise RuntimeError("Crossref API returned no usable records.")
            write_json(raw_path, payload)
        except Exception as exc:
            if not raw_path.exists():
                raise
            print(f"[ingestion] Crossref API unavailable ({exc}); falling back to offline snapshot.")
            payload = None

    if payload is None:
        payload = read_json(raw_path)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot records va map thanh `PaperRecord`."""
    fields = PaperRecord.__dataclass_fields__
    return [PaperRecord(**{key: row.get(key) for key in fields}) for row in read_json(Path(path))]
