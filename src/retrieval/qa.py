from __future__ import annotations

from dataclasses import dataclass
import re

from core.config import Settings
from core.utils import first_sentence
from retrieval.index import LocalEmbeddingIndex, SearchResult

# Cosine similarity toi thieu cua top-1 de coi la cau hoi thuoc corpus.
# Do thuc te: cau trong test set >= 0.53, cau ngoai domain <= 0.14.
MIN_RELEVANCE_SCORE = 0.3
NO_ANSWER = "I don't know from the indexed corpus."


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answer: str
    retrieved_doc_ids: list[str]
    retrieved_contexts: list[str]
    retrieved_titles: list[str]


def _extract_answer(question: str, top_result: SearchResult) -> str:
    lowered = question.lower()
    metadata = top_result.metadata
    if "who authored" in lowered or "list the authors" in lowered:
        return metadata["authors_joined"]
    if "when was" in lowered or "publication date" in lowered or "published on" in lowered:
        return metadata["published"]
    if "what categories" in lowered:
        return metadata["categories_joined"]
    return first_sentence(metadata["summary"])


def answer_question(question: str, settings: Settings, index: LocalEmbeddingIndex, top_k: int | None = None) -> AnswerResult:
    title_match = re.search(r"'([^']+)'", question)
    exact = index.lookup(title_match.group(1)) if title_match else None
    retrieved = index.search(question, top_k=top_k)
    if exact:
        exact_result = SearchResult(
            paper_id=exact["paper_id"],
            title=exact["title"],
            score=1.0,
            content=exact["content"],
            metadata=exact["metadata"],
        )
        deduped = [exact_result] + [item for item in retrieved if item.paper_id != exact_result.paper_id]
        retrieved = deduped[: (top_k or settings.top_k)]
    # Van tra ve retrieved docs de do retrieval hit, nhung khong trich cau tra loi tu tai lieu khong lien quan.
    if not retrieved or retrieved[0].score < MIN_RELEVANCE_SCORE:
        answer = NO_ANSWER
    else:
        answer = _extract_answer(question, retrieved[0])
    return AnswerResult(
        question=question,
        answer=answer,
        retrieved_doc_ids=[item.paper_id for item in retrieved],
        retrieved_contexts=[item.content for item in retrieved],
        retrieved_titles=[item.title for item in retrieved],
    )
