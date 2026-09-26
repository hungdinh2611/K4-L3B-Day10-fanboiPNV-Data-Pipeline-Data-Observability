from __future__ import annotations

from pathlib import Path
from typing import Any
import logging

import great_expectations as gx
import great_expectations.expectations as gxe
from great_expectations.data_context.types.base import ProgressBarsConfig
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_ROWS = 5
MAX_ROWS = 5000
MIN_SUMMARY_CHARS = 30
MAX_STALE_RATIO = 0.25
REQUIRED_NOT_NULL = ("paper_id", "title", "text_for_embedding")
GX_COLUMNS = ("paper_id", "title", "summary", "text_for_embedding", "published", "age_days")

logging.getLogger("great_expectations").setLevel(logging.ERROR)


def _build_expectations() -> list[gx.expectations.Expectation]:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROWS, max_value=MAX_ROWS),
        *[gxe.ExpectColumnValuesToNotBeNull(column=column) for column in REQUIRED_NOT_NULL],
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_CHARS),
    ]


def _run_gx_expectations(df: pd.DataFrame, report_name: str) -> list[dict[str, Any]]:
    """Chay 4 hang rao expectations bang GX 1.x Ephemeral Context."""
    gx_df = df.reindex(columns=list(GX_COLUMNS)).copy()
    # GX khong xu ly tot kieu object hon hop; ep text ve str, giu None/NaN de check null.
    for column in ("paper_id", "title", "summary", "text_for_embedding", "published"):
        gx_df[column] = gx_df[column].where(gx_df[column].isna(), gx_df[column].astype(str))

    context = gx.get_context(mode="ephemeral")
    context.variables.progress_bars = ProgressBarsConfig(globally=False)
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": gx_df})

    suite = context.suites.add(gx.ExpectationSuite(name=f"papers_suite_{report_name}"))
    for expectation in _build_expectations():
        suite.add_expectation(expectation)

    validation = batch.validate(suite)
    checks: list[dict[str, Any]] = []
    for result in validation.results:
        config = result.expectation_config
        observed = result.result or {}
        checks.append(
            {
                "expectation": config.type,
                "column": config.kwargs.get("column"),
                "success": bool(result.success),
                "observed_value": observed.get("observed_value"),
                "unexpected_count": observed.get("unexpected_count"),
                "unexpected_percent": observed.get("unexpected_percent"),
            }
        )
    return checks


def evaluate_freshness_sla(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Tinh ti le bai bao cu (age_days > threshold); vuot 25% thi is_fresh = False."""
    threshold = settings.freshness_threshold_days
    total_rows = int(len(df))
    published = pd.to_datetime(df.get("published"), errors="coerce") if total_rows else pd.Series(dtype="datetime64[ns]")
    age_days = pd.to_numeric(df.get("age_days"), errors="coerce") if total_rows else pd.Series(dtype=float)

    stale_rows = int((age_days > threshold).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    return {
        "checked_at": now_utc().isoformat(),
        "threshold_days": threshold,
        "max_stale_ratio": MAX_STALE_RATIO,
        "latest_published": published.max().strftime("%Y-%m-%d") if published.notna().any() else None,
        "oldest_published": published.min().strftime("%Y-%m-%d") if published.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "max_age_days": int(age_days.max()) if age_days.notna().any() else None,
        "is_fresh": total_rows > 0 and stale_ratio <= MAX_STALE_RATIO,
    }


def _quality_report_path(settings: Settings, report_name: str) -> Path:
    known = {
        "baseline": settings.paths.baseline_quality_report,
        "corrupted": settings.paths.corrupted_quality_report,
    }
    return known.get(report_name, settings.paths.quality_dir / f"{report_name}_quality_report.json")


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Observability Gate: 4 expectations GX + freshness SLA, ghi ket qua vao `data/quality/`."""
    checks = _run_gx_expectations(df, report_name)
    freshness = evaluate_freshness_sla(df, settings)
    expectations_success = all(check["success"] for check in checks)

    result = {
        "stage": report_name,
        "checked_at": freshness["checked_at"],
        "row_count": int(len(df)),
        "success": expectations_success and freshness["is_fresh"],
        "expectations_success": expectations_success,
        "expectations_passed": sum(check["success"] for check in checks),
        "expectations_total": len(checks),
        "failed_expectations": [
            f"{check['expectation']}({check['column']})" if check["column"] else check["expectation"]
            for check in checks
            if not check["success"]
        ],
        "checks": checks,
        "freshness": freshness,
    }
    write_json(_quality_report_path(settings, report_name), result)
    return result


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report va ghi JSON."""
    payload = evaluate_freshness_sla(df, settings)
    write_json(Path(report_path), payload)
    return payload
