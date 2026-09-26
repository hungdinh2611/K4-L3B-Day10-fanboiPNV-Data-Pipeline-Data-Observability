from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings, load_settings, normalized_provider
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def save_clean_artifacts(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _content_to_text(content: Any) -> str:
    """Gemini 3 tra ve list content blocks (kem signature); chi giu phan text."""
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        ).strip()
    return str(content)


def _run_agent_demo(settings: Settings, index: LocalEmbeddingIndex, test_set: list[dict[str, Any]]) -> None:
    """Demo agent tren vai cau hoi (chi chay khi co LLM that)."""
    if normalized_provider(settings) == "mock":
        return
    try:
        from retrieval.agent import build_agent, run_agent_question

        agent = build_agent(settings, index)
        answers = [
            {"question": item["question"], "answer": _content_to_text(run_agent_question(agent, item["question"]))}
            for item in test_set[:2]
        ]
        write_json(settings.paths.demo_answers, answers)
        print(f"[phase1] Agent demo answers saved to {settings.paths.demo_answers}")
    except Exception as exc:
        print(f"[phase1] Agent demo skipped: {exc}")


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Ingest -> Clean -> Index ChromaDB -> Testset -> Evaluate -> Quality Gate -> Report."""
    run_date = now_utc()

    print("[phase1] 1/6 Ingest raw records")
    records = fetch_source_records(settings)

    print("[phase1] 2/6 Clean data")
    clean_df = build_clean_dataframe(records, run_date)
    save_clean_artifacts(clean_df, settings.paths.clean_csv, settings.paths.clean_json)

    print("[phase1] 3/6 Build ChromaDB index")
    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)

    print("[phase1] 4/6 Build or load test set")
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)

    print("[phase1] 5/6 Evaluate baseline RAG")
    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )

    print("[phase1] 6/6 Quality gate & freshness")
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_records": len(records),
        "clean_rows": len(clean_df),
        "test_questions": len(test_set),
        "embedding_model": settings.embedding_model,
        "collection": index.collection_name,
        "run_date": run_date.date().isoformat(),
    }
    generate_phase1_report(settings.paths.baseline_report, source_summary, bundle.summary, quality, freshness)
    _run_agent_demo(settings, index, test_set)

    metrics = bundle.summary
    print("\n=== Phase 1 Baseline ===")
    print(f"Clean rows          : {len(clean_df)}")
    print(f"Retrieval Hit Rate  : {metrics['retrieval_hit_rate']:.4f}")
    print(f"Mean Token F1       : {metrics['mean_token_f1']:.4f}")
    print(f"Judge Accuracy      : {metrics['judge_accuracy']:.4f}")
    print(f"Quality Gate        : {'PASS' if quality['success'] else 'FAIL'}")
    print(f"Freshness           : {'FRESH' if freshness['is_fresh'] else 'STALE'}")
    print(f"Report              : {settings.paths.baseline_report}")
    return {"metrics": metrics, "quality": quality, "freshness": freshness, "clean_rows": len(clean_df)}


def main() -> None:
    run_phase1_pipeline(load_settings())
