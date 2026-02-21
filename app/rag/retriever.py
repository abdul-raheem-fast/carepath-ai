from pathlib import Path
from typing import List, Tuple

from app.backend.config import get_settings

try:
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    LANGCHAIN_AVAILABLE = True
except Exception:  # pragma: no cover
    LANGCHAIN_AVAILABLE = False
    Document = object  # type: ignore[assignment]


def _read_kb_documents() -> List[str]:
    settings = get_settings()
    kb_dir = Path(settings.knowledge_base_dir)
    docs: List[str] = []
    for path in kb_dir.glob("*.txt"):
        docs.append(path.read_text(encoding="utf-8"))
    if not docs:
        docs.append(
            "Medication adherence improves when reminders and family support are used. "
            "Patients should seek care for severe symptoms or rapid worsening."
        )
    return docs


def retrieve_context(question: str, report_text: str, top_k: int = 3) -> Tuple[str, List[str]]:
    docs = [report_text[:3000], *_read_kb_documents()]
    if LANGCHAIN_AVAILABLE:
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
        chunks: List[Document] = []
        for d in docs:
            chunks.extend(splitter.create_documents([d]))
        # Lightweight deterministic "embedding" placeholder avoided for external API calls.
        # For MVP reliability, we use lexical match fallback even when langchain exists.
    scored = sorted(
        docs,
        key=lambda d: _simple_score(question, d),
        reverse=True,
    )[:top_k]
    citations = [s[:180].replace("\n", " ") for s in scored]
    context = "\n\n".join(scored)
    return context, citations


def _simple_score(question: str, text: str) -> int:
    q_tokens = {w for w in question.lower().split() if len(w) > 2}
    t = text.lower()
    return sum(1 for token in q_tokens if token in t)
