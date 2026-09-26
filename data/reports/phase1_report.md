# Phase 1 Report — Baseline Data Pipeline

_Generated at 2026-09-26T03:10:25.191954+00:00_

## 1. Source Summary

| Field | Value |
|---|---|
| source_api | Crossref REST API |
| query | agentic retrieval augmented generation large language model |
| filter | from-pub-date:2026-03-30,has-abstract:true |
| raw_records | 24 |
| clean_rows | 24 |
| test_questions | 10 |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| collection | papers-baseline |
| run_date | 2026-09-26 |

## 2. Retrieval & Evaluation Metrics

| Metric | Value |
|---|---|
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 1.0000 |
| Judge Accuracy | 1.0000 |
| Mean Judge Score (1-5) | 5 |
| Samples | 10 |

## 3. Data Quality Gate (Great Expectations 1.x)

- Gate status: **✅ PASS**
- Expectations passed: 6/6

| Expectation | Column | Result | Observed | Unexpected |
|---|---|---|---|---|
| `expect_table_row_count_to_be_between` | — | ✅ PASS | 24 | — |
| `expect_column_values_to_not_be_null` | paper_id | ✅ PASS | — | 0 |
| `expect_column_values_to_be_unique` | paper_id | ✅ PASS | — | 0 |
| `expect_column_values_to_not_be_null` | title | ✅ PASS | — | 0 |
| `expect_column_values_to_not_be_null` | text_for_embedding | ✅ PASS | — | 0 |
| `expect_column_value_lengths_to_be_between` | summary | ✅ PASS | — | 0 |

## 4. Freshness

- Latest published: 2026-07-22
- Oldest published: 2026-03-28
- Stale rows (> 180 days): 1/24 (4.2%)
- Is fresh (stale ratio ≤ 25%): **✅ PASS**
