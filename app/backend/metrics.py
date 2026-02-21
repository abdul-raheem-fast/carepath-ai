import re
from typing import Iterable, List


def estimate_readability_score(text: str) -> float:
    """Return a simple 0-100 understandability estimate (higher is easier)."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return 0.0
    sentences = [s for s in re.split(r"[.!?]+", cleaned) if s.strip()]
    words = re.findall(r"[A-Za-z]+", cleaned)
    if not sentences or not words:
        return 0.0

    sentence_len = len(words) / max(len(sentences), 1)
    avg_word_len = sum(len(w) for w in words) / len(words)

    # Penalize very long sentences and words to approximate readability.
    score = 100.0 - (sentence_len * 1.8) - (avg_word_len * 8.5)
    return round(max(0.0, min(100.0, score)), 2)


def citation_coverage(question: str, citations: Iterable[str]) -> float:
    q_tokens = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", question)}
    if not q_tokens:
        return 0.0
    blob = " ".join(citations).lower()
    hit_count = sum(1 for token in q_tokens if token in blob)
    return round(hit_count / len(q_tokens), 3)


def grounded_answer(citations: List[str], generated: str) -> str:
    if not citations:
        return (
            "I cannot find enough supporting evidence in your uploaded report and approved knowledge snippets. "
            "Please ask a more specific question from the report."
        )
    return generated
