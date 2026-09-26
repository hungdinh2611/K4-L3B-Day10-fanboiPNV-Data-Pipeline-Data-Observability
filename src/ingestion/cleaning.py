from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "authors_joined",
    "categories_joined",
    "published",
    "updated",
    "age_days",
    "summary_chars",
    "abs_url",
    "pdf_url",
    "comment",
    "text_for_embedding",
]


def _clean_list(values) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    items = [normalize_whitespace(str(value)) for value in values if value is not None]
    return list(dict.fromkeys(item for item in items if item))


def _clean_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return normalize_whitespace(str(value))


def build_text_for_embedding(row) -> str:
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed."""
    rows = []
    for record in records:
        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        rows.append(
            {
                "paper_id": _clean_text(record.paper_id).lower(),
                "title": _clean_text(record.title),
                "summary": _clean_text(record.summary),
                "authors": authors,
                "categories": categories,
                "primary_category": _clean_text(record.primary_category) or (categories[0] if categories else ""),
                "published": record.published,
                "updated": record.updated,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
            }
        )

    df = pd.DataFrame(rows, columns=[c for c in CLEAN_COLUMNS if c not in {
        "authors_joined", "categories_joined", "age_days", "summary_chars", "text_for_embedding"
    }])
    if df.empty:
        return pd.DataFrame(columns=CLEAN_COLUMNS)

    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    updated = pd.to_datetime(df["updated"], errors="coerce", utc=True).fillna(published)
    run_ts = pd.Timestamp(run_date)
    run_ts = run_ts.tz_localize("UTC") if run_ts.tzinfo is None else run_ts.tz_convert("UTC")

    df["published"] = published.dt.strftime("%Y-%m-%d")
    df["updated"] = updated.dt.strftime("%Y-%m-%d")
    df["age_days"] = (run_ts.normalize() - published.dt.normalize()).dt.days
    df["authors_joined"] = df["authors"].apply(compact_join)
    df["categories_joined"] = df["categories"].apply(compact_join)
    df["summary_chars"] = df["summary"].str.len()

    # Bo dong xau: thieu khoa, thieu title/summary hoac ngay khong parse duoc.
    valid = (
        df["paper_id"].str.len().gt(0)
        & df["title"].str.len().gt(0)
        & df["summary"].str.len().gt(0)
        & published.notna()
    )
    df = df[valid].copy()

    df = df.drop_duplicates(subset="paper_id", keep="first")
    df["age_days"] = df["age_days"].astype(int)
    df["text_for_embedding"] = df.apply(build_text_for_embedding, axis=1)

    df = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df[CLEAN_COLUMNS]
