# RaUP MVP

AI-guided pre-visit questionnaire (anamnesis) for one-on-one clinical consultations (nutrition, physiotherapy, psychology). Master's thesis project for the AI for Healthcare program.

## Stack

- Python + Streamlit, deployed on Streamlit Community Cloud (free)
- Supabase (Postgres + Storage) from day one — no intermediate local phase. Goal: everything running in the cloud so external clinicians can try it.
- LLM: MedGemma 4B-it (Google, open weights), hosted on RunPod Serverless with automatic scale-to-zero (shuts itself down when idle, wakes itself up on the next request; zero manual start/stop). See [DECISIONS.md](DECISIONS.md) D-006 to D-008.
- The LLM client sits behind a swappable interface: MedGemma is trained for medical comprehension, not specifically for following strict conversational instructions, so it may lean more toward clinical-sounding language than a general-purpose model. If the guardrails aren't enough, it must be replaceable without rewriting the app.

## CLOSED scope (this week)

1. **Clinician screen**: choose "First visit" or "Follow-up" mode and an optional "consultation reason" field. Generates a link/code for the patient.
2. **Patient screen**: LLM-guided adaptive questionnaire (5-7 min for a first visit, 3-5 for a follow-up), designed for mobile. Allows uploading documents **without processing them**.
3. **Report for the clinician**: executive summary, threshold-based warning signals, areas to explore further.
4. **Regulatory restriction** (see rules).

**Out of scope**: clinician login, personalization, PDF extraction, EHR integration. Don't add any of this without explicit approval.

## Rules

### Regulatory (MDR Class I) — non-negotiable
- The system **NEVER** suggests diagnoses, treatments, regimens, dosages, or clinical interpretations, either to the patient or to the clinician.
- The report only **summarizes what the patient reported**, flags warning signals against explicit thresholds, and suggests *areas to explore further* (what to ask about), never *what to do* or *what the patient has*.
- LLM prompts must explicitly forbid this, and the output is validated/filtered before being shown. There must be tests that verify this.
- Warning signals come from deterministic thresholds defined in code/config, not from the LLM's free judgment, and are grounded in validated screening instruments per specialty (PHQ-9, GAD-7, C-SSRS, MUST, SCOFF, NICE red flags, STarT Back — see D-009). Exact cutoff figures are confirmed against the current guideline, not from memory.

### Data and security
- **Synthetic data only.** Never real patient data.
- Don't commit `.env`, API keys, Supabase/LLM-hosting credentials, or any data. Secrets only via environment variables / `st.secrets` on Streamlit Cloud.
- Uploaded documents are stored as-is (Supabase Storage); never read or processed.

### Process
- **Log every technical decision in DECISIONS.md** (date, options considered, reasoning). Will be used for the thesis writeup.
- Propose a plan and wait for approval before implementing new blocks.
- The persistence layer (Supabase) and the LLM client (MedGemma) sit behind their own interfaces, so the implementation can be swapped without touching business logic.
- Language: code (identifiers, comments, file names), documentation (README/CLAUDE.md/DECISIONS.md), and LLM system prompts (developer-facing instructions) are all in English — this repo doubles as a portfolio piece read by recruiters on GitHub (see D-013, D-014). The one absolute exception: all text the end user actually reads — UI labels, buttons, messages, and the questionnaire questions themselves once built — stays in **Spanish**, exactly as authored, never auto-translated or rephrased, since this is a real pilot with Spanish-speaking dietitians. Supabase table/column names also stay in Spanish, since they're a schema contract already applied in production (see D-013).
- Commits only when the user asks for them.
