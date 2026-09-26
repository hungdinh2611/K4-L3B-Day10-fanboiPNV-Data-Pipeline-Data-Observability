from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import build_comparison_rows, generate_corruption_report
from pipelines.phase1 import run_phase1_pipeline, save_clean_artifacts
from retrieval.index import LocalEmbeddingIndex


def repair_from_raw_snapshot(settings: Settings) -> pd.DataFrame:
    """Idempotent recovery: dung lai clean data tu raw snapshot (Lineage Anchor), ghi de ban hong.

    Chay bao nhieu lan cung cho ra cung mot ket qua vi chi phu thuoc vao raw records.
    """
    records = load_raw_records(settings.paths.raw_records_json)
    repaired = build_clean_dataframe(records, now_utc())
    save_clean_artifacts(repaired, settings.paths.repaired_clean_csv, settings.paths.repaired_clean_json)
    return repaired


def _evaluate_stage(settings: Settings, df: pd.DataFrame, embeddings_path, metrics_path, answers_path) -> dict[str, Any]:
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    return evaluate_pipeline(settings, index, settings.paths.eval_testset, metrics_path, answers_path).summary


def _print_comparison(baseline: dict, corrupted: dict, repaired: dict, corrupted_q: dict, repaired_q: dict) -> None:
    header = f"{'Metric':<24}{'Baseline':>12}{'Corrupted':>12}{'Repaired':>12}"
    print("\n=== Baseline vs Corrupted vs Repaired ===")
    print(header)
    print("-" * len(header))
    for label, base, cor, rep in build_comparison_rows(baseline, corrupted, repaired):
        print(f"{label:<24}{base:>12.4f}{cor:>12.4f}{rep:>12.4f}")
    gate = lambda q: "PASS" if q["success"] else "FAIL"  # noqa: E731
    print(f"{'Quality Gate':<24}{'PASS':>12}{gate(corrupted_q):>12}{gate(repaired_q):>12}")


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Corrupt -> evaluate (silent failure) -> repair tu raw snapshot -> re-evaluate -> compare."""
    paths = settings.paths
    if not (paths.baseline_metrics.exists() and paths.clean_json.exists() and paths.eval_testset.exists()):
        print("[corruption] Baseline artifacts missing, running phase 1 first.")
        run_phase1_pipeline(settings)

    print("[corruption] 1/5 Load baseline metrics & clean data")
    baseline_metrics = read_json(paths.baseline_metrics)
    clean_df = pd.DataFrame(read_json(paths.clean_json))

    print("[corruption] 2/5 Corrupt data & evaluate (silent failure)")
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    save_clean_artifacts(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    corrupted_metrics = _evaluate_stage(
        settings, corrupted_df, paths.corrupted_embeddings_json, paths.corrupted_metrics, paths.corrupted_answers
    )

    print("[corruption] 3/5 Quality gate on corrupted data")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, paths.quality_dir / "corrupted_freshness_report.json"
    )

    print("[corruption] 4/5 Repair from raw snapshot & re-evaluate")
    repaired_df = repair_from_raw_snapshot(settings)
    repaired_metrics = _evaluate_stage(
        settings, repaired_df, paths.repaired_embeddings_json, paths.repaired_metrics, paths.repaired_answers
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, paths.quality_dir / "repaired_freshness_report.json"
    )

    print("[corruption] 5/5 Write comparison report")
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )

    _print_comparison(baseline_metrics, corrupted_metrics, repaired_metrics, corrupted_quality, repaired_quality)
    print(f"\nReport: {paths.comparison_report}")
    return {
        "baseline": baseline_metrics,
        "corrupted": corrupted_metrics,
        "repaired": repaired_metrics,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
    }


def main() -> None:
    run_corruption_flow_pipeline(load_settings())
