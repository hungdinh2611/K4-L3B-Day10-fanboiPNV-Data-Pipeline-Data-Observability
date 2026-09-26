from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import build_text_for_embedding

SEED = 42
DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_ROWS = 3
NOISE_ROWS = 3
TRUNCATE_TITLE_ROWS = 3
TRUNCATE_TITLE_CHARS = 7
STALE_DATE_ROWS = 6
STALE_SHIFT_DAYS = 365
DUPLICATE_ROWS = 3
NOISE_TEXT = "#@!$%^ lorem ipsum ~~~ 0xDEADBEEF ###"


def _sample_ids(df: pd.DataFrame, n: int, exclude: set[str], salt: int) -> list[str]:
    pool = df[~df["paper_id"].isin(exclude)]
    n = min(n, len(pool))
    return pool.sample(n=n, random_state=SEED + salt)["paper_id"].tolist() if n else []


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Gia lap 6 dang data corruption tren clean dataframe va ghi corruption log."""
    corrupted = df.copy().reset_index(drop=True)
    log: list[dict[str, Any]] = []

    # 1. Drop latest records: mat 20% bai bao moi nhat.
    n_drop = max(1, int(round(len(corrupted) * DROP_LATEST_RATIO)))
    latest = corrupted.sort_values("published", ascending=False).head(n_drop)
    for _, row in latest.iterrows():
        log.append({"type": "drop_latest_records", "paper_id": row["paper_id"], "before": row["published"], "after": None})
    corrupted = corrupted[~corrupted["paper_id"].isin(latest["paper_id"])].reset_index(drop=True)

    touched: set[str] = set()

    # 2. Blank summary.
    for pid in _sample_ids(corrupted, BLANK_SUMMARY_ROWS, touched, 2):
        mask = corrupted["paper_id"] == pid
        log.append({"type": "blank_summary", "paper_id": pid, "before": corrupted.loc[mask, "summary"].iat[0], "after": ""})
        corrupted.loc[mask, "summary"] = ""
        touched.add(pid)

    # 3. Inject noise vao summary.
    for pid in _sample_ids(corrupted, NOISE_ROWS, touched, 3):
        mask = corrupted["paper_id"] == pid
        before = corrupted.loc[mask, "summary"].iat[0]
        after = f"{NOISE_TEXT} {before[::-1]} {NOISE_TEXT}"
        log.append({"type": "inject_noise", "paper_id": pid, "before": before, "after": after})
        corrupted.loc[mask, "summary"] = after
        touched.add(pid)

    # 4. Truncate title xuong duoi 8 ky tu.
    for pid in _sample_ids(corrupted, TRUNCATE_TITLE_ROWS, touched, 4):
        mask = corrupted["paper_id"] == pid
        before = corrupted.loc[mask, "title"].iat[0]
        after = before[:TRUNCATE_TITLE_CHARS]
        log.append({"type": "truncate_title", "paper_id": pid, "before": before, "after": after})
        corrupted.loc[mask, "title"] = after
        touched.add(pid)

    # 5. Stale date: lui ngay xuat ban 365 ngay.
    for pid in _sample_ids(corrupted, STALE_DATE_ROWS, touched, 5):
        mask = corrupted["paper_id"] == pid
        before = corrupted.loc[mask, "published"].iat[0]
        after = (pd.Timestamp(before) - pd.Timedelta(days=STALE_SHIFT_DAYS)).strftime("%Y-%m-%d")
        log.append({"type": "stale_date", "paper_id": pid, "before": before, "after": after})
        corrupted.loc[mask, "published"] = after
        corrupted.loc[mask, "age_days"] = corrupted.loc[mask, "age_days"] + STALE_SHIFT_DAYS
        touched.add(pid)

    # 6. Duplicate rows.
    dup_ids = _sample_ids(corrupted, DUPLICATE_ROWS, set(), 6)
    for pid in dup_ids:
        log.append({"type": "duplicate_rows", "paper_id": pid, "before": 1, "after": 2})
    corrupted = pd.concat([corrupted, corrupted[corrupted["paper_id"].isin(dup_ids)]], ignore_index=True)

    # 7. Rebuild cot phu thuoc de loi "lan" vao embedding.
    corrupted["summary_chars"] = corrupted["summary"].str.len()
    corrupted["text_for_embedding"] = corrupted.apply(build_text_for_embedding, axis=1)

    # 8. Ghi corruption log.
    counts: dict[str, int] = {}
    for entry in log:
        counts[entry["type"]] = counts.get(entry["type"], 0) + 1
    write_json(
        Path(output_log_path),
        {
            "created_at": now_utc().isoformat(),
            "seed": SEED,
            "input_rows": int(len(df)),
            "output_rows": int(len(corrupted)),
            "counts": counts,
            "changes": log,
        },
    )
    return corrupted
