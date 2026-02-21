# CarePath AI Hackathon Submission

## Innovation
- Combines OCR + clinical entity extraction + multilingual patient communication in one flow.
- Generates explainable care plans and risk scores from uploaded medical text.
- Grounded chatbot answers only from uploaded report + approved medical snippets, with citations.

## Real-world Impact
- Helps patients understand and follow care instructions.
- Reduces medication non-adherence by proactive reminders.
- Surfaces red flags to encourage timely clinician contact.

## Technical Details
- **Frontend:** Streamlit
- **Backend:** FastAPI + SQLite + APScheduler
- **NLP/ML:** spaCy/rule-based extraction, risk scoring heuristics with explainable factors
- **RAG:** LangChain + FAISS-ready retrieval module, lexical fallback for reliability
- **OCR:** pdfplumber (PDF), pytesseract (images)
- **Testing:** pytest smoke tests for parser/recommender/API
- **Config/Safety:** `.env` config, no hardcoded keys, file size limits, disclaimer in responses

## Reproducibility
1. `pip install -r requirements.txt`
2. `copy .env.example .env`
3. Start backend: `uvicorn app.backend.main:app --reload`
4. Start frontend: `streamlit run app/frontend/streamlit_app.py`
5. Optional seeded demo: `python scripts/seed_demo.py`
6. Docker alternative: `docker-compose up --build`

## Judging Criteria Alignment
- **Generative AI Innovation:** Grounded multilingual summaries + contextual Q&A with citations.
- **Real-world Impact:** Directly improves patient comprehension and continuity of care.
- **Technical Implementation:** Modular architecture, API + UI + scheduler + test suite + containerization.
- **Documentation & Reproducibility:** Complete README, architecture diagram, setup scripts, sample data.
