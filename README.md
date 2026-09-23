# RaUP MVP

AI-guided pre-visit questionnaire for one-on-one clinical consultations. Live pilot: **[pilot-raup.streamlit.app](https://pilot-raup.streamlit.app)**. See [CLAUDE.md](CLAUDE.md) for scope and rules, and [DECISIONS.md](DECISIONS.md) for the reasoning behind every technical decision.

## Status

Step 7 done: deployed to Streamlit Community Cloud, connected to this public GitHub repo (see D-023). All 6 previous steps are done and verified against the real MedGemma endpoint — persistence, clinician/patient screens, the LLM client with its regulatory safety filter, the adaptive questionnaire, and the report engine (executive summary, deterministic nutrition alerts, areas to explore). The first real user test (D-023) already found and fixed three issues no test suite caught: an answer box that didn't clear between questions, stray quote marks in a model-generated question, and a questionnaire that ended slightly early. Currently in manual testing before opening it up to external clinicians for feedback — still no real patients.

## Local setup

1. **Python 3.11+** (not preinstalled on this machine — install it before continuing).
2. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```
3. Create a project on [supabase.com](https://supabase.com) (free tier) and run [supabase/schema.sql](supabase/schema.sql) in its SQL editor.
4. Copy `.env.example` to `.env` and fill in `SUPABASE_URL` / `SUPABASE_KEY` (project Settings > API).
5. Run the tests: `pytest`
6. Start the app: `streamlit run app.py` — should show the clinician panel (or the configuration warning if `.env` is missing).

## Structure

Language convention (see D-013, D-014): code identifiers, comments, and documentation are in English; everything the end user sees (UI text, questionnaire questions) stays in Spanish, unmodified — this is a real pilot with Spanish-speaking dietitians.

- `raup/models.py` — domain entities (Session, Answer, DocumentMetadata, Report, Alert).
- `raup/repository/base.py` — repository interfaces (the contract the rest of the app relies on).
- `raup/repository/supabase_repo.py` — Supabase implementation.
- `raup/codes.py` — generates the short code the clinician shares with the patient.
- `raup/config.py` — configuration loading (`.env` locally, secrets on Streamlit Cloud).
- `raup/ui/professional.py` — clinician screen (new session, look up by code).
- `raup/ui/patient.py` — patient screen (code-based access).
- `app.py` — routes between the two screens based on `?code=` in the URL (see D-011).
- `raup/llm/base.py` — `LLMClient` interface.
- `raup/llm/prompts.py` — shared safety preamble every system prompt must include.
- `raup/llm/guardrails.py` — deterministic filter that blocks diagnostic/interpretive/prescriptive language (see D-016).
- `raup/llm/safe_client.py` — `generate_safely`, the only path Steps 5/6 should use to call the LLM.
- `raup/llm/medgemma_client.py` — MedGemma via RunPod Serverless, verified live (see D-017).
- `raup/questionnaire/budget.py` — the time/question-count cutoffs (see D-020).
- `raup/questionnaire/objectives.py` — the information checklist the questionnaire aims to cover.
- `raup/questionnaire/prompts.py` — builds the questionnaire's task-specific prompts.
- `raup/questionnaire/protocol.py` — parses the model's per-turn `QUESTION/TYPE/DONE` response.
- `raup/questionnaire/engine.py` — `get_next_step`, ties the above together; the one entry point `raup/ui/patient.py` uses.
- `raup/report/extraction.py` — pulls raw facts (never computed values) out of the transcript (see D-022).
- `raup/report/alerts.py` — deterministic MUST/SCOFF-inspired threshold checks, nutrition-only for now (D-009, D-022).
- `raup/report/summary.py` — the declarative executive summary.
- `raup/report/areas.py` — up to 5 areas to explore, capped in code as well as in the prompt.
- `raup/report/engine.py` — `generate_report`, ties the above together; the one entry point `raup/ui/patient.py` uses.
- `tests/fakes.py` — in-memory repository doubles and `FakeLLMClient`, for tests only.
- `tests/apps/` — "harness" scripts to test the screens with `AppTest` (see D-012).
- `supabase/schema.sql` — database schema (table/column names kept in Spanish on purpose, see D-013), to run on the Supabase project.
