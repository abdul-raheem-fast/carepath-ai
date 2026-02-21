# CarePath AI Architecture

```mermaid
flowchart LR
    U[User] --> S[Streamlit Frontend]
    S --> B[FastAPI Backend]
    B --> P[OCR + Parser]
    B --> R[Recommender + Risk]
    B --> G[RAG Retriever]
    G --> K[(Approved KB)]
    B --> D[(SQLite)]
    B --> A[APScheduler]
```

## Components
- `app/frontend`: Streamlit UI for upload, summary, care plan, and chat.
- `app/backend`: FastAPI API, DB access, scheduler, validation.
- `app/ml`: Text extraction, entity extraction, multilingual generation fallback, recommendation, risk score.
- `app/rag`: Context retrieval and citation snippets.
- `app/data`: SQLite DB, uploads, approved knowledge snippets.