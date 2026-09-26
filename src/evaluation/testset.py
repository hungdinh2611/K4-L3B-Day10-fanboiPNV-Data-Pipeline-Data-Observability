from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

TEST_SET_SIZE = 10
MIN_DOCUMENTS = 5
# Cau hoi dung cac cum tu ma `retrieval.qa._extract_answer` nhan dien duoc.
QUESTION_TEMPLATES = {
    "summary": ("What is the summary of the paper '{title}'?", lambda row: first_sentence(row["summary"])),
    "authors": ("Who authored the paper '{title}'?", lambda row: row["authors_joined"]),
    "date": ("When was the paper '{title}' published?", lambda row: row["published"]),
    "categories": ("What categories does the paper '{title}' belong to?", lambda row: row["categories_joined"]),
}


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao 10 cau hoi Ground Truth phan bo deu qua 4 dang tu cleaned dataframe."""
    usable = df.dropna(subset=["paper_id", "title", "summary"])
    usable = usable[usable["summary"].str.len() > 0].drop_duplicates(subset="paper_id")
    if len(usable) < MIN_DOCUMENTS:
        raise ValueError(f"Need at least {MIN_DOCUMENTS} clean documents to build a test set, got {len(usable)}.")

    # Chon paper dai dien trai deu tren toan corpus (moi/cu) de test set on dinh.
    usable = usable.sort_values("paper_id").reset_index(drop=True)
    step = len(usable) / TEST_SET_SIZE
    picks = [usable.iloc[int(i * step)] for i in range(TEST_SET_SIZE)]

    question_types = list(QUESTION_TEMPLATES)
    test_set: list[dict[str, Any]] = []
    for i, row in enumerate(picks):
        question_type = question_types[i % len(question_types)]
        template, ground_truth = QUESTION_TEMPLATES[question_type]
        test_set.append(
            {
                "id": f"eval_{i + 1:03d}",
                "question_type": question_type,
                "question": template.format(title=row["title"]),
                "ground_truth": str(ground_truth(row)),
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    write_json(Path(output_path), test_set)
    return test_set
