# Corruption Report — Baseline vs Corrupted vs Repaired

_Generated at 2026-09-26T05:07:52.477844+00:00_

## 1. Performance Comparison

| Metric | Baseline | Corrupted | Repaired | Δ Corrupted | Δ Repaired |
|---|---|---|---|---|---|
| Retrieval Hit Rate | 1.0000 | 0.9000 | 1.0000 | -0.1000 | +0.0000 |
| Mean Token F1 | 1.0000 | 0.9000 | 1.0000 | -0.1000 | +0.0000 |
| Judge Accuracy | 1.0000 | 0.9000 | 1.0000 | -0.1000 | +0.0000 |
| Mean Judge Score (1-5) | 5 | 4.6000 | 5 | -0.4000 | +0.0000 |

## 2. Quality Gate Status

| Stage | Gate | Rows | Failed expectations | Fresh |
|---|---|---|---|---|
| Corrupted | ❌ FAIL | 22 | `expect_column_values_to_be_unique(paper_id)`, `expect_column_value_lengths_to_be_between(summary)` | ❌ FAIL |
| Repaired | ✅ PASS | 24 | — | ✅ PASS |

### Corrupted — expectation details

- Gate status: **❌ FAIL**
- Expectations passed: 4/6

| Expectation | Column | Result | Observed | Unexpected |
|---|---|---|---|---|
| `expect_table_row_count_to_be_between` | — | ✅ PASS | 22 | — |
| `expect_column_values_to_not_be_null` | paper_id | ✅ PASS | — | 0 |
| `expect_column_values_to_be_unique` | paper_id | ❌ FAIL | — | 6 |
| `expect_column_values_to_not_be_null` | title | ✅ PASS | — | 0 |
| `expect_column_values_to_not_be_null` | text_for_embedding | ✅ PASS | — | 0 |
| `expect_column_value_lengths_to_be_between` | summary | ❌ FAIL | — | 4 |

### Repaired — expectation details

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

## 3. Freshness

**Corrupted**

- Latest published: 2026-06-12
- Oldest published: 2025-05-02
- Stale rows (> 180 days): 7/22 (31.8%)
- Is fresh (stale ratio ≤ 25%): **❌ FAIL**

**Repaired**

- Latest published: 2026-07-22
- Oldest published: 2026-03-28
- Stale rows (> 180 days): 1/24 (4.2%)
- Is fresh (stale ratio ≤ 25%): **✅ PASS**

## 4. Conclusion

- Corrupted data was still indexed and answered without runtime errors (**silent failure**); only the quality gate and metrics reveal the damage.
- Repair from raw snapshot fully restored baseline retrieval performance.
