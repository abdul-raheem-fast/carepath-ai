# CarePath AI — Hackathon Submission

**Event:** Generative AI Healthcare Hackathon 2026
**Team:** Abdul Raheem (Solo)
**Live Demo:** https://carepath-ai.streamlit.app/
**Repository:** https://github.com/abdul-raheem-fast/carepath-ai

---

## Problem Statement

Medication non-adherence costs the global healthcare system over **$500 billion annually** and causes nearly **125,000 preventable deaths** per year in the US alone. In Pakistan and South Asia, the problem is amplified by:

- Complex discharge summaries written in clinical English that patients cannot understand
- Language barriers (Urdu-speaking patients receiving English-only documents)
- Lack of structured daily guidance after discharge
- No easy mechanism for patients to ask follow-up questions about their reports

**CarePath AI** directly addresses these gaps by converting any uploaded medical document into a clear, actionable, bilingual patient care guide — powered by Generative AI.

---

## Innovation

### Generative AI at the Core
CarePath AI uses **Groq-hosted Llama 3.1 8B** to:
1. Simplify clinical language into plain patient-friendly English (4–6 sentence summaries)
2. Translate summaries into Urdu with culturally appropriate phrasing
3. Answer patient questions grounded strictly in the uploaded report (RAG-based Q&A)
4. Generate personalized adherence coaching when the simulator is used

### Novel Feature Combination
No existing consumer app combines all of:
- OCR (PDF + image + text) → clinical NLP extraction
- Bilingual (EN + Urdu) LLM summarization
- Explainable risk scoring
- Medication safety scanning
- Recovery scorecard (multi-dimensional readiness)
- Adherence impact simulation with AI tips
- One-click professional PDF handout export
- Grounded source-cited chatbot

### Robust Fallback Architecture
The system is designed to **never fail silently**:
- If Groq API is unavailable → deterministic rule-based summary activates
- If Tesseract OCR is missing (e.g., Streamlit Cloud) → RapidOCR (pure Python) takes over
- If FAISS index is empty → lexical keyword search provides citations
- All error paths return a useful patient-facing result

---

## Real-World Impact

### Target Population
- Post-discharge hospital patients in Pakistan and South Asia
- Low-literacy or elderly patients who struggle with medical documents
- Caregivers managing complex multi-medication regimens

### Measurable Outcomes
| Intervention | Expected Impact |
|---|---|
| Plain-language summaries | Reduces confusion → better instruction compliance |
| Urdu translation | Removes language barrier for ~230M Urdu speakers |
| Daily care plan | Structures medication timing → reduces missed doses |
| Red-flag warnings | Educates patients on urgent symptoms → earlier hospital visits |
| Adherence simulator | Motivates behavior change through data visualization |

### Scalability
The architecture is cloud-native and stateless. A single Streamlit Cloud deployment serves unlimited concurrent users. Adding new languages requires only a new prompt template — no architectural changes.

---

## Technical Details

### Architecture Overview
```
Patient → [File Upload (PDF/Image/Text)]
         → OCR Pipeline (pdfplumber / pytesseract / RapidOCR)
         → Clinical Entity Extractor (spaCy + regex rules)
         → Groq LLM (Llama 3.1-8B-Instant)
              ├── English Summary
              ├── Urdu Translation
              └── Care Plan Generation
         → RAG Module (LangChain + FAISS / lexical fallback)
              └── Grounded Q&A Chatbot
         → Risk Scorer (heuristic + weighted features)
         → Medication Safety Scanner
         → Recovery Scorecard Builder
         → Adherence Simulator
         → PDF Handout Generator (ReportLab)
         → SQLite (logs, metrics, reminders)
```

### Key Technical Decisions

**1. Self-contained Streamlit deployment**
Rather than maintaining a separate FastAPI backend on a different service (with CORS, auth tokens, and two deployment configs), all ML logic is imported directly into the Streamlit app. This eliminates `ConnectionError` issues and simplifies Streamlit Cloud deployment to a single service.

**2. LLM provider abstraction**
`LLMProvider` is a Python `Protocol`. `GroqLLM`, `OpenAILLM`, and `FallbackLLM` all satisfy it. Switching LLM vendors requires changing one environment variable — zero code changes.

**3. Direct `os.environ` reads in `llm.py`**
`pydantic-settings` caches settings via `lru_cache`. On Streamlit Cloud, secrets are injected after module import, so cached settings miss the API key. Solved by reading `os.environ["GROQ_API_KEY"]` directly on every `get_llm_provider()` call, bypassing the cache.

**4. OCR fallback chain**
`pytesseract` requires a system binary not available on Streamlit Cloud. Added `rapidocr_onnxruntime` (pure Python, no system deps) as a transparent fallback, preserving full OCR capability on all hosting environments.

**5. Urdu rendering**
`arabic-reshaper` + `python-bidi` handle correct right-to-left glyph shaping for Urdu in the web UI. The PDF uses a graceful English fallback with an explanatory note, since embedding Arabic fonts in ReportLab requires paid font licensing.

### Stack Summary
| Component | Technology | Version |
|---|---|---|
| UI | Streamlit | 1.54 |
| LLM | Groq / Llama 3.1 | 8B-Instant |
| OCR | pdfplumber + pytesseract + RapidOCR | latest |
| NLP | spaCy, regex | en_core_web_sm |
| RAG | LangChain + FAISS | 0.3.x |
| PDF | ReportLab Platypus | 4.x |
| DB | SQLite | built-in |
| Scheduler | APScheduler | 3.x |
| Tests | pytest | 8.x |
| Container | Docker + Compose | 3.8 |

### Evaluation Metrics (live-tracked in Admin panel)
- **Process Latency** (ms) — upload-to-output wall-clock time
- **Summary Readability** (Flesch-Kincaid proxy, 0–100)
- **Chat Citation Coverage** (0–1) — fraction of chatbot answers with source snippets
- **Adherence Simulation engagement** — slider interaction count per session

---

## Reproducibility

### Local Setup (< 10 min)
```bash
git clone https://github.com/abdul-raheem-fast/carepath-ai.git
cd carepath-ai
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env        # add GROQ_API_KEY
streamlit run app/frontend/streamlit_app.py
```

### Docker (one command)
```bash
docker-compose up --build
# Frontend: http://localhost:8501
# Backend API: http://localhost:8000/docs
```

### Demo data
```bash
python scripts/seed_demo.py
```
Loads three pre-built clinical reports (hypertension + diabetes, post-cardiac-surgery, diabetic nephropathy) so judges can test the full pipeline without uploading their own files.

### Tests
```bash
pytest -q
```
Covers: entity extraction, care plan generation, risk scoring, PDF handout export, API endpoints.

---

## Judging Criteria Alignment

| Criterion | Evidence |
|---|---|
| **Generative AI Innovation** | Groq Llama 3.1 for bilingual summarization + RAG-grounded chatbot + adherence coaching |
| **Real-World Impact** | Targets 230M Urdu speakers; addresses medication non-adherence ($500B annual cost) |
| **Technical Implementation** | End-to-end OCR→NLP→LLM→RAG→PDF pipeline; fallback chains; live observability |
| **Documentation & Reproducibility** | README + architecture diagram + sample data + Docker + test suite |
