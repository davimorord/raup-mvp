# Technical decision log — RaUP MVP

Format for each entry: date, context, options considered, decision, and reasoning. Meant to be reused for the thesis writeup.

---

## D-001 · 2026-09-21 · Base stack
- **Context**: one-week MVP, single developer, thesis project.
- **Options**: Streamlit; FastAPI + JS frontend; Flask + templates.
- **Decision**: Python + Streamlit.
- **Reasoning**: maximum prototyping speed, a single language, enough for the two required screens. Accepted limitation: less control over mobile design.

## D-002 · 2026-09-21 · ~~Local persistence at first, no Supabase~~ (SUPERSEDED by D-006)
- **Context**: wanted to validate the flow before investing in infrastructure.
- **Options**: Supabase from the start; local JSON; local SQLite.
- **Original decision**: local storage (JSON or SQLite), behind a repository interface, with a later migration to Supabase.
- **Reasoning**: fewer dependencies and less setup this week; the interface avoids rewriting logic when migrating.
- **2026-09-22 revision**: the user sets having everything running in the cloud from the start as the goal, so external clinicians can try it. See D-006.

## D-006 · 2026-09-22 · Cloud-first from day one: Supabase + Streamlit Community Cloud
- **Context**: the thesis needs external clinicians to be able to try the app; asking them to run it locally isn't viable. Explicit user goal: "everything running in the cloud" and very low or zero cost.
- **Options**: local (JSON/SQLite) with a later migration; Supabase from day 1; another BaaS (Firebase).
- **Decision**: Supabase (Postgres + Storage) from the first implementation step, no intermediate local phase. The app deploys on Streamlit Community Cloud (free: 1 GB RAM, 1 CPU, up to 3 concurrent users, sleeps after 12h idle and wakes itself on the next visit).
- **Reasoning**: Supabase's free tier covers the MVP's needs (free project, pauses after ~1 week without requests, wakes itself back up); avoids rewriting the persistence layer mid-thesis; Streamlit Community Cloud is free and enough for scheduled test sessions (not for high concurrent traffic).
- **Consequence**: a repository interface is kept regardless (not coupling logic directly to Supabase), for design hygiene and to ease testing, even though there's no pending migration anymore.
- **Source**: [Streamlit Community Cloud — status and limits](https://docs.streamlit.io/deploy/streamlit-community-cloud/status).

## D-003 · 2026-09-21 · Synthetic data only
- **Decision**: no real patient data is used at any stage of the MVP.
- **Reasoning**: avoid GDPR obligations around health data (a special category) while there's no legal basis, DPIA, or adequate infrastructure in place.

## D-004 · 2026-09-21 · MDR Class I regulatory restriction
- **Context**: the software must not be classified as a higher-risk medical device.
- **Decision**: the system never suggests diagnoses or treatments. It only summarizes what was reported, flags threshold-based alerts, and proposes areas to explore further.
- **Reasoning**: keep the product within the low-classification perimeter. Implemented via restrictive prompts, an output filter, and tests.
- **Consequence**: alerts are based on deterministic thresholds, not on the LLM's free judgment.

## D-005 · 2026-09-21 · Version control and exclusions
- **Decision**: git initialized with a `.gitignore` that excludes `.env`, secrets, virtual environments, databases, uploads, and the `data/` directory.
- **Reasoning**: avoid leaking keys or data (even synthetic ones, to build the right habit from the start).

## D-007 · 2026-09-22 · LLM: MedGemma
- **Context**: a thesis requirement (AI for Healthcare program) and a "very cheap or free" cost constraint.
- **Options**: Claude (pay-per-token API); MedGemma (Google, open weights, health-focused); another general-purpose open model (e.g. Gemma 3).
- **Decision**: MedGemma, **4B-it** variant (lighter than the 27B one, needed for hosting to be viable on a minimal budget).
- **Reasoning**: no licensing cost; aligned with the thesis's focus (a health model). The risk trade-off versus a general-purpose Claude/Gemma is accepted: MedGemma is trained/evaluated for medical comprehension (imaging, clinical QA), not specifically for following strict conversational instructions like "never diagnose," so it may lean more toward clinical-sounding language. Mitigated by strengthening the output filter and the guardrail tests (Step 3 of the plan) and keeping the LLM client behind a swappable interface.
- **Source**: [MedGemma — Get started, Google for Developers](https://developers.google.com/health-ai-developer-foundations/medgemma/get-started).

## D-008 · 2026-09-22 (revised 2026-09-22) · MedGemma hosting: serverless GPU with automatic scale-to-zero
- **Context**: MedGemma has no pay-per-token serverless API (unlike Gemini). An "always-on" dedicated endpoint (Vertex AI Model Garden, HF Inference Endpoints in fixed mode) bills per GPU-hour even with no traffic: ~$0.50–3.40/h on Vertex (T4/L4 + management fee), $0.033–5/h on HF Endpoints. The genuinely free option (Hugging Face Spaces + ZeroGPU) gives no availability or latency guarantees, a risk that isn't acceptable for live testing with clinicians.
- **Original decision (same date)**: a minimal-cost dedicated GPU, manually turned on/off during scheduled test windows.
- **Revision**: the user requires minimal human execution — zero manual start/stop. Confirmed that **automatic scale-to-zero** exists: the GPU shuts itself down after a period with no requests and wakes itself up on the next one, with no human intervention and no cost while idle. Supported by Hugging Face Inference Endpoints (`min_replica_count=0`, sleeps after 15 min without requests), RunPod Serverless (bills per second of actual compute, scales workers down to zero automatically), and Vertex AI (`ScaleToZeroSpec`, a newer feature with more configuration pieces).
- **Final decision**: **RunPod Serverless**, with the MedGemma-4B-it weights baked into the container image to minimize cold start. Per-second billing, zero cost at rest, zero clicks to start or stop.
- **Reasoning**: a product built specifically for serverless GPU inference (unlike Vertex, which adapts its general-purpose autoscaling to this case); shorter cold start than HF Endpoints if the model is baked into the image instead of downloaded on every boot; no extra management fee like Vertex's.
- **Accepted trade-off**: the first request after an idle period will have extra latency (cold start, on the order of tens of seconds) while the GPU boots. Mitigated by showing a "loading model" message in the UI instead of leaving the app looking hung. It's the inherent cost of "zero human execution + minimal cost": there's no way to have both without some latency on first use.
- **Sources**: [RunPod Serverless — pricing and cold starts](https://docs.runpod.io/serverless/pricing), [Hugging Face Inference Endpoints — autoscaling](https://huggingface.co/docs/inference-endpoints/en/guides/autoscaling), [Vertex AI — autoscaling and scale-to-zero](https://docs.cloud.google.com/vertex-ai/docs/predictions/autoscaling).

## D-009 · 2026-09-22 · Alert thresholds grounded in recent evidence
- **Context**: the user requires that warning signals not be an arbitrary criterion, but grounded in the most recent available clinical evidence.
- **Decision**: thresholds will be based on validated screening instruments per specialty, not invented thresholds:
  - Psychology: PHQ-9 (depression), GAD-7 (anxiety), a self-harm ideation item / Columbia-type protocol (C-SSRS) for suicide risk.
  - Nutrition: unintentional weight loss (MUST-type criteria — Malnutrition Universal Screening Tool), SCOFF-type eating-behavior screening.
  - Physiotherapy: red flags for serious pathology (NICE guidelines), STarT Back-type stratification tools.
- **Reasoning**: these are validated, widely cited instruments; using them instead of homegrown thresholds strengthens regulatory legitimacy (MDR Class I: deterministic threshold-based alerts, not LLM judgment) and gives academic traceability for the thesis writeup.
- **Pending**: confirm in Step 6 (alert engine design) the exact cutoff figures and their citations from the current guideline/version, via a targeted search at that point.

## D-010 · 2026-09-22 · No Row Level Security in the MVP
- **Context**: when creating the Supabase tables (Step 1), a decision was needed on whether to enable Postgres RLS (Row Level Security), which restricts which rows each request can read/write.
- **Options**: enable RLS with policies keyed on the session code; leave the tables open (no RLS) during the MVP.
- **Decision**: no RLS for now. The only access control is the session code itself (unpredictable but not a strong credential), and the tables remain accessible with the project's `anon` key.
- **Reasoning**: there's no clinician login (out of scope, see CLAUDE.md) and only synthetic data is used (D-003), so the real risk is low at this stage. Adding RLS now would be premature complexity with no authentication model to tie it to.
- **Consequence / limitation to document in the thesis writeup**: this schema is not fit for real patient data as-is. Before handling real data it would need: RLS with explicit policies, a stronger authentication mechanism than the short code, and Storage policies for the `documentos` bucket (currently undefined, see supabase/schema.sql).

## D-011 · 2026-09-22 · Clinician/patient routing by query param, no native multipage
- **Context**: no login (out of scope); the clinician screen needs to be distinguished from the patient screen within the same app.
- **Options**: Streamlit's native `pages/` multipage mode (with sidebar navigation); a single app.py that routes based on a URL parameter.
- **Decision**: a single `app.py` that reads `st.query_params["code"]`: no code → clinician screen; with a code → patient screen.
- **Reasoning**: multipage mode's automatic sidebar navigation would show links to both screens to either actor, which doesn't make sense (the patient shouldn't see or touch the clinician screen) and breaks the mobile-first design required for the patient. With a query param the patient only sees their own clean screen.
- **Consequence**: the patient interface depends on the clinician sharing the code/link correctly; there's no way to "discover" the clinician screen from the patient's link, which is the intended access barrier (see D-010).

## D-012 · 2026-09-22 · UI tests with `streamlit.testing.v1.AppTest`
- **Context**: Step 2 introduces the first Streamlit screens; needed to decide whether they're only checked by hand or also tested automatically.
- **Options**: manual verification only; `AppTest` (Streamlit's official testing framework, simulates clicks/inputs with no browser) against in-memory doubles.
- **Decision**: `AppTest` against "harness" scripts (`tests/apps/harness_*.py`) that inject the in-memory repositories from `tests/fakes.py` into `st.session_state`, so the test suite doesn't depend on Supabase credentials.
- **Reasoning**: allows verifying the real flow (create session → code appears; invalid code → error; valid code → status changes) in CI/locally with no network or secrets, with the same rigor as the Step 1 repository tests.

## D-013 · 2026-09-22 · Code in English, product-facing text in Spanish
- **Context**: the project started with identifiers and comments in Spanish (D-001 to D-012). It's a real pilot with Spanish-speaking dietitians, but the code itself is more maintainable and standard in English (usual industry convention, more legible for any future collaboration outside the team).
- **Decision**: everything "of code" is translated to English — Python variable, function, class, and file names, and comments/docstrings. Everything "user-facing" is explicitly kept in Spanish — UI text (labels, buttons, success/error messages seen by the clinician or the patient), and the questionnaire questions once they exist (Step 5).
- **Explicit scope of this pass** (so it's clear what was left untouched and why):
  - **Unchanged**: table and column names in `supabase/schema.sql`, and the `.value` of the `ConsultationMode`/`SessionStatus` enums (`"primera_consulta"`, `"creada"`, etc.). They're a schema contract already applied to the real Supabase project; translating them would require recreating the tables in production. Left as future work if wanted later.
  - **Translated**: the URL parameter, from `?codigo=` to `?code=` — it's a technical parameter name, not content the user reads.
  - **Documentation** (README.md, CLAUDE.md, DECISIONS.md): kept in Spanish at the time (the existing rule, see CLAUDE.md), only fixed the file paths that changed name. Superseded the same day — see D-014.
- **Reasoning**: cleanly separate "product language" (Spanish, because the end users are Spanish clinicians) from "code language" (English, standard technical convention), avoiding the mix of both criteria that existed before.
- **Files renamed**: `raup/modelos.py`→`raup/models.py`, `raup/codigos.py`→`raup/codes.py`, `raup/repositorio/`→`raup/repository/`, `raup/ui/profesional.py`→`raup/ui/professional.py`, `raup/ui/paciente.py`→`raup/ui/patient.py`, and their equivalents under `tests/`. The root package `raup/` is kept as-is (it's the product name, not a term to translate).

## D-014 · 2026-09-22 · Documentation in English too (portfolio-facing)
- **Context**: right after D-013 (code in English, docs still in Spanish per the original rule), the user points out this repo is also a GitHub portfolio piece: anything a recruiter might read there needs to be in English.
- **Options**: keep README/CLAUDE.md/DECISIONS.md in Spanish (original rule, ties directly into the Spanish-language thesis writeup); translate them to English (readable by a non-Spanish-speaking recruiter browsing the repo); maintain both languages in parallel (extra upkeep burden for a one-person, one-week MVP).
- **Decision**: translate README.md, CLAUDE.md, DECISIONES.md (this file), and `.env.example` to English. Product-facing text (UI, questionnaire) stays Spanish, unaffected — that decision (D-013) isn't reopened here, it concerns end users, not GitHub readers. The Supabase schema and the enum `.value`s also stay Spanish (D-013's live-infrastructure exception still applies; not revisited today).
- **Reasoning**: these documents' primary audience shifts from "just me, for the thesis" to "me, for the thesis, *and* anyone evaluating this repo as a work sample." English serves both: the user can read and translate relevant parts into the Spanish thesis writeup regardless (a formal academic memoria is written and adapted by hand, not copy-pasted from this log), while a recruiter can't read Spanish documentation at all. Keeping two parallel language versions was rejected as unnecessary upkeep for a one-week MVP with a single maintainer.
- **Consequence**: from this point on, all new DECISIONS.md entries, README.md updates, and CLAUDE.md rules are written in English.

## D-015 · 2026-09-22 · Rename DECISIONES.md → DECISIONS.md
- **Context**: D-014 translated this file's content to English but left its filename in Spanish — an inconsistency the user caught immediately.
- **Decision**: rename `DECISIONES.md` to `DECISIONS.md`, update every reference to it (README.md, CLAUDE.md, and the `DECISIONES.md`-pointing comments/docstrings across `raup/`), and replace the leftover Spanish "Paso N" step references with "Step N" everywhere they appeared in English-language text (code comments, docstrings, this log). Left untouched: "Paso N" mentions embedded inside actual Spanish UI strings (`raup/ui/patient.py`, `raup/ui/professional.py`) and inside `supabase/schema.sql`, both out of scope per D-013.
- **Reasoning**: a recruiter-facing filename should match the recruiter-facing content; leaving a lone Spanish filename undermines the point of D-014.

## D-016 · 2026-09-22 · Guardrail enforcement: deterministic pattern filter, not an LLM judge
- **Context**: Step 3 needs a way to guarantee the MDR Class I rule (never diagnose, never prescribe, never clinically interpret) actually holds, not just a request the model can ignore.
- **Options**: rely on the system prompt alone; use a second LLM call as a judge/classifier over the first model's output; use a deterministic pattern/keyword filter.
- **Decision**: two independent layers. (1) `raup/llm/prompts.py`'s `SAFETY_PREAMBLE`, prepended to every system prompt — a request, not a guarantee. (2) `raup/llm/guardrails.py`'s `check_output`, a deterministic regex-based filter over every LLM response, in Spanish (the real output language) — flags diagnostic, clinically-interpretive, and prescriptive/dosage language. `raup/llm/safe_client.py`'s `generate_safely` ties them together: retries up to 3 times with a stronger reminder, then raises `UnsafeOutputError` rather than ever returning unsafe text.
- **Reasoning**: an LLM-as-judge second call is itself a non-deterministic model that could be wrong or inconsistent, which undermines the same "auditable, deterministic mechanism" argument already used for alert thresholds (D-009) — the whole point of MDR Class I compliance here is a mechanism a regulator or examiner can read and verify, not "we asked another model to check." A pattern filter is auditable, testable, and reproducible, at the cost of being narrower than true language understanding.
- **Known limitation** (to document in the thesis writeup): the pattern list in `guardrails.py` was built from plausible unsafe phrasings, not from real MedGemma output — there was no live endpoint yet (see D-008, D-017). It's a first pass, not exhaustive, and false negatives are possible until it's re-tuned against real model output in Step 4+. The test suite in `tests/test_guardrails.py` is the living spec of what it currently catches.

## D-017 · 2026-09-22 (verified 2026-09-23) · MedGemmaClient built ahead of the live RunPod endpoint
- **Context**: Step 3 needs a concrete `LLMClient` implementation for MedGemma, but the actual RunPod Serverless endpoint isn't deployed yet (that's Step 4) — unlike Supabase, this integration couldn't be smoke-tested against the real thing.
- **Decision**: implement `raup/llm/medgemma_client.py` against RunPod's documented serverless contract (`POST /v2/{endpoint_id}/runsync`) and the conventional vLLM-worker request/response shape (`input.messages`, `output.choices[0].message.content`), clearly marked DRAFT/UNVERIFIED in its docstring. Tests (`tests/test_medgemma_client.py`) mock the HTTP call to check the request/response handling logic, not the real contract.
- **Reasoning**: unblocks building `LLMClient`-dependent code (guardrails, the safe wrapper, and eventually Steps 5/6) without waiting on infrastructure work; the `LLMClient` interface (D-007) means swapping in the real contract later, once Step 4 reveals it, is a one-file change.
- **Risk accepted**: the request/response shape may not match the real deployed handler exactly. This must be verified with a live smoke test in Step 4, the same way `raup/repository/supabase_repo.py` was verified against real Supabase in Step 1.
- **2026-09-23 verification — two assumptions were wrong**: tested against the real endpoint (`ip3lce4062igap`, `runpod-workers/worker-vllm`) and found (1) sampling parameters (`max_tokens`, `temperature`) must be nested under `input.sampling_params`, not flat in `input`; (2) `output` in the job result is a **list**, so the completion is `output[0].choices[0].message.content`, not `output.choices[0]...`. Both fixed in `medgemma_client.py`, and `tests/test_medgemma_client.py` now pins the verified shape.
- **Bigger correction — sync route abandoned**: the original design called `/runsync`. A real cold start measured **~256s**, far past the ~100s edge timeout RunPod's synchronous routes sit behind (a Cloudflare 524 past that point). Switched to the async pattern: `POST /run` (returns a job id immediately) + poll `GET /status/{job_id}` up to a 420s budget. This is now the permanent design, not a temporary workaround — cold starts are inherent to scale-to-zero (D-008) and any synchronous call will hit this wall.
- **Full stack verified end to end**: `MedGemmaClient` → `generate_safely` (safety preamble + guardrail check) → real MedGemma-4B-it on the live endpoint, called from plain Python (not just the RunPod MCP tools). Prompted with a physiotherapy-consultation summary task, the model returned "El paciente refiere dolor lumbar de tres semanas de duración." — a plain restatement of what the patient said, no diagnosis, no interpretation, no treatment — and passed the guardrail on the first attempt, no retry needed.

## D-018 · 2026-09-23 · MAX_MODEL_LEN capped at 8192 (down from MedGemma's 131072 default)
- **Context**: the first live deployment attempt crash-looped — `CUDA out of memory` during the vLLM worker's own fitness/benchmark check. Root cause: MedGemma supports up to 131,072 tokens of context, and vLLM pre-allocates KV cache sized for the full context window by default, which alone consumed ~12.5 GiB of the RTX A5000's 24 GiB, leaving no margin.
- **Decision**: set `MAX_MODEL_LEN=8192` and `GPU_MEMORY_UTILIZATION=0.90` as endpoint env vars. Verified live: weights 8.57 GiB + KV cache 11.39 GiB fit comfortably within 24 GiB.
- **Reasoning**: the pre-visit questionnaire (Step 5) and report generation (Step 6) are short-context tasks — a handful of Q&A turns plus a safety preamble, nowhere near 8192 tokens, let alone 131,072. Paying for headroom the app will never use was both the direct cause of the crash loop and pure waste.
- **Operational gotcha hit while fixing this, worth recording**: after updating the endpoint's env vars in place, the already-running (crash-looping) worker kept being selected for new jobs ahead of freshly-booted healthy workers, because `workersMax: 1` capped the endpoint to a single active worker and the scheduler didn't evict the unhealthy one in favor of the healthy ones sitting idle. Bumping `workersMax` temporarily did not reliably resolve it either. **Deleting and recreating the endpoint from scratch** (with the corrected env vars baked in from the first deploy) was faster and cleaner than fighting the in-place rollover. Noted here in case Step 4+ infra work hits the same thing.

## D-019 · 2026-09-23 · Specialty as free text, not a closed enum
- **Context**: the professional screen (Step 2) never asked which specialty a session was for, but the questionnaire engine (Step 5) and the alert engine (Step 6, per D-009) both need it. First instinct: a 3-option enum matching D-009's specialties (nutrition/physiotherapy/psychology).
- **Decision**: `Session.specialty` is a plain string, not an enum, defaulting to "Nutrición" in both the UI and the `especialidad` column. The clinician can overwrite it with anything.
- **Reasoning**: the user corrected this directly — the first real pilot is nutrition-dietitian-focused, and the field exists mainly to give the questionnaire engine's prompt the right context and label, not to gate a fixed set of code paths. Locking it to 3 options would block trying the app with any other kind of clinician during the pilot.
- **Consequence flagged for Step 6**: the alert engine (D-009) is designed around three named specialties with specific validated instruments (PHQ-9/GAD-7/C-SSRS, MUST/SCOFF, NICE red flags/STarT Back). With `specialty` now free text, Step 6 will need a matching strategy (e.g. case-insensitive match against the three known specialties, falling back to no specialty-specific instrument otherwise) rather than a clean enum switch. Not blocking now since the pilot is nutrition-only, but noted so it isn't a surprise.

## D-020 · 2026-09-23 · Adaptive questionnaire paced by a time budget, not a fixed question count
- **Context**: first proposal was a fixed number of questions (7 first visit / 5 follow-up). The user pushed back: a fixed count either wastes the patient's time when answers are rich, or — worse — cuts the interview short before covering the necessary ground when answers are terse, since terse answers need more follow-up questions to extract the same information.
- **Decision**: pace by wall-clock time instead, matching CLAUDE.md's original scope (5-7 min first visit, 3-5 min follow-up) rather than a question tally. Concretely:
  - A **hard, deterministic time cutoff** enforced in code (`raup/questionnaire/budget.py`, checked before ever calling the LLM): 7 min first visit, 5 min follow-up.
  - The **last 60 seconds** of that budget trigger a "start wrapping up" instruction injected into the prompt.
  - A generous **question-count safety valve** (15 first visit / 10 follow-up) as a second, independent cutoff — not a target, purely to stop a pathological non-terminating interview regardless of the clock.
  - Within those bounds, the LLM decides per turn whether it has enough information, guided by a checklist of information objectives (`raup/questionnaire/objectives.py`: current situation, history, incidents, antecedents, medication, origin, symptoms and severity) rather than a question count.
  - Questions are tagged `YES_NO` or `TEXT` by the model itself, so the UI can render a quick two-button answer instead of a text box whenever a quick answer captures what's needed — mixing both keeps patient effort low without sacrificing the open-ended questions that need the patient's own words.
- **Reasoning**: "we know what's going on, what happened, incidents, history, medication, the problem's origin, symptoms and their levels" (the user's own framing) is a coverage goal, not a count goal — success is defined by what the clinician gets out of it, not by how many questions were asked.
- **Mechanism**: each turn the LLM responds in a fixed three-line format (`QUESTION:` / `TYPE:` / `DONE:`), parsed by `raup/questionnaire/protocol.py`. Parsing is deliberately lenient — an unparseable response falls back to "not done, treat the whole response as a free-text question" rather than breaking the flow, the same tolerant-fallback philosophy as the safety retry logic (D-016).
- **Verified live**: the real MedGemma endpoint followed the three-line format correctly on the first try, prompted with a nutrition-consultation reason ("quiero perder peso, llevo unos meses con mucha fatiga"), producing a sensible open-ended opening question.

## D-021 · 2026-09-23 · Document upload wired to Supabase Storage
- **Context**: `DocumentMetadata` and the `documentos` table existed since Step 1, but nothing actually uploaded file bytes anywhere — Storage access policies were explicitly deferred to Step 5 (see D-010).
- **Decision**: `SupabaseDocumentRepository.upload_file` uploads directly to the `documentos` Storage bucket (path `{session_id}/{random_id}-{filename}`), and `supabase/schema.sql` now grants the `anon` role insert + select on that bucket's objects. The patient screen exposes this as an optional, non-blocking file uploader shown alongside every question — not gated behind a specific step — since a patient might want to attach a lab report at any point.
- **Reasoning**: matches the project's existing no-RLS stance for the MVP (D-010) — the session code is still the only real access control, and only synthetic data/documents are ever uploaded. Verified live: uploaded and cleaned up a real test file against the live bucket.
- **Consequence, same as D-010**: not fit for real patient documents as-is; would need per-session-scoped Storage policies (not just bucket-wide) before handling real data.

## D-022 · 2026-09-23 · Report engine: extraction (LLM) + thresholds (code), MUST/SCOFF simplified for nutrition
- **Context**: Step 6 needs an executive summary, deterministic alerts (D-009), and areas to explore. The questionnaire (Step 5) is fully adaptive/LLM-driven, so there's no guaranteed structured field to compare against a threshold the way a fixed form would give — the same tension noted in D-019 for specialty matching.
- **Decision — two-layer alert design**: `raup/report/extraction.py` asks the LLM (via `generate_safely`, same safety layer as everywhere else) to pull specific facts out of the transcript into a fixed line-by-line format — a comprehension task, explicitly forbidden from inferring or computing anything not stated. `raup/report/alerts.py` then compares those facts against the fixed, cited MUST/SCOFF cutoffs (D-009) in plain Python — the LLM never decides what counts as alarming, only what the patient said.
- **Nutrition-only for now** (per D-019): `compute_alerts` returns nothing unless `specialty` case-insensitively contains "nutrici". Psychology/physiotherapy instruments from D-009 aren't implemented.
- **Simplified instruments, documented honestly**:
  - **MUST**: weight-loss component only (<5% low, 5-10% medium, >=10% high). Full MUST also scores BMI and an acute-disease effect on intake, neither reliably collected by an open-ended questionnaire — not implemented.
  - **SCOFF**: 4 of the 5 validated items (omits the weight-loss item, folded into the MUST check instead, to avoid extracting weight loss twice); cutoff kept at >=2 affirmative. This is an approximate derivative, not the literal 5-item validated instrument — its psychometric properties (sensitivity/specificity) don't strictly transfer.
- **Two real bugs found via a live MedGemma smoke test, both fixed and re-verified**:
  1. **The model can't be trusted to compute a percentage.** Told to report "8 kilos lost from a base of 70kg" as `WEIGHT_LOSS_PERCENT`, MedGemma-4B returned the literal "8" — the kilogram figure, uncomputed — misclassifying a case that should be MUST_ALTO (11.4%, >=10%) as MUST_MEDIO. Fixed by never asking the LLM to compute anything: it now only extracts `WEIGHT_LOSS_KG` and `WEIGHT_BEFORE_KG` (numbers it can read directly), and `ExtractedFields.weight_loss_percent` computes the division in Python. Re-verified live: correctly produced 11.4286% → MUST_ALTO.
  2. **"Areas to explore" fell into a repetition loop.** With no cap, the model generated dozens of near-identical items ("¿Ha notado algún cambio en su relación con la tecnología/la política/el arte...?") until it hit the token limit mid-word. Fixed with an explicit "at most 5" instruction in the prompt *and* a hard `[:5]` truncation in code — the same "never trust the model to self-limit, enforce the boundary in code" pattern as the questionnaire's time/question budget (D-020). Re-verified live: exactly 5 relevant items.
- **Reasoning for the general pattern**: this reinforces the project's throughline (D-009, D-016, D-020) — anywhere a number or a stopping point matters, the LLM supplies raw material (facts, a draft, a judgment call within bounds) and code makes the actual determination. A 4B model is good at reading comprehension and language generation; it is demonstrably not reliable at arithmetic or self-imposed limits, and this session's testing caught both failure modes before they reached a clinician.
- **When the report is generated**: automatically, the moment the patient's questionnaire reaches `done` (`raup/ui/patient.py`), so it's ready before the clinician looks it up — not generated on-demand. Wrapped in a broad try/except: if generation fails for any reason, the patient still sees the thank-you screen, and the clinician's lookup screen falls back to showing the raw, unsummarized transcript (added in this step for exactly this reason) rather than losing the data.

## D-023 · 2026-09-23 · Deployment (Step 7) and fixes from the first real user test
- **Deployment**: public GitHub repo ([davimorord/raup-mvp](https://github.com/davimorord/raup-mvp)), deployed on Streamlit Community Cloud at `pilot-raup.streamlit.app`. GitHub CLI auth via OAuth device flow failed repeatedly in this environment (`context deadline exceeded` / `expired_token` on three attempts) for reasons not fully diagnosed; a classic personal access token with the `repo` scope, passed via the `GH_TOKEN` environment variable, worked reliably and is the documented fallback. Streamlit Cloud's own sharing default needed an explicit check — "This app is public and searchable" under Settings → Sharing — since an unauthenticated fetch initially appeared to hit a login wall (this turned out to be how Streamlit Cloud's session bootstrap looks to a non-browser HTTP client, not an actual access restriction; confirmed working via a real incognito-window test).
- **Three real issues found in the very first live user test (not caught by any test suite) and fixed**:
  1. **The patient's answer box didn't clear between questions.** `st.text_area` and its `st.form` had fixed, session-scoped keys, so Streamlit treated it as the same widget across reruns and kept showing the previous answer. Fixed by folding the question number into every per-question widget's key (`raup/ui/patient.py`), so each new question gets a genuinely fresh widget.
  2. **The model occasionally wrapped its question in literal quote marks** (`QUESTION: "¿...?"`) despite the format not asking for them, showing up oddly in the UI. Fixed with a small `_strip_wrapping_quotes` step in `raup/questionnaire/protocol.py` (removes one matching pair only, never a quote that's part of the sentence itself).
  3. **The questionnaire ended a little early**, without following up on a concrete, directly nutrition-relevant lead the patient raised in their very first answer ("solo gano peso a pesar de seguir la misma dieta que antes"). This is a judgment-quality issue, not a bug with a clean fix — tightened the `DONE: YES` criterion in `raup/questionnaire/prompts.py` to require that nothing the patient already raised is left unexplored, not just that the fixed objective checklist is "adequately" covered. Not independently re-verified live yet (needs another real run to confirm it actually reduces premature stops) — flagged below.
- **A genuinely correct behavior worth recording, not a bug**: the same test transcript included the patient stating their own doctor had previously diagnosed "menopausia prematura." The executive summary reported this ("el paciente indica haber sido diagnosticado... por su médico") and the guardrail filter (D-016) correctly let it through — relaying a diagnosis the patient says they already received from their own doctor is reported speech, not this system diagnosing anything, and the regulatory rule (D-004) is about the latter.

---

## Still to decide
- Exact link/code mechanism for the patient
- Psychology/physiotherapy alert instruments (D-009, D-022) — not implemented, pilot is nutrition-only
- Whether the guardrail pattern list (D-016) needs expansion based on more real MedGemma output
- Whether the SCOFF-derived alert (D-022) needs re-validation or relabeling given it's 4 of 5 items, not the literal instrument
- Whether D-023's "don't leave a patient-raised lead unexplored" prompt change actually reduces premature questionnaire endings — needs another live run to confirm
