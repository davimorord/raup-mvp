"""Builds the task-specific prompts for the adaptive questionnaire.

Only the task instructions live here — the regulatory safety preamble is
added separately by raup.llm.safe_client.generate_safely, so it's never
duplicated or (worse) accidentally left out by a caller.
"""

from __future__ import annotations

from raup.models import Answer, ConsultationMode, Session
from raup.questionnaire.budget import QuestionnaireBudget

_MODE_DESCRIPTIONS = {
    ConsultationMode.FIRST_VISIT: "first visit",
    ConsultationMode.FOLLOW_UP: "follow-up",
}

_RESPONSE_FORMAT = """
Respond in exactly this format, nothing else — do not wrap the question in quote marks:
QUESTION: <the question, in Spanish>
TYPE: YES_NO or TEXT
DONE: YES only if the objectives above are adequately covered AND nothing the patient already \
mentioned is left unexplored (or you were told to wrap up); NO otherwise. When DONE is YES, \
QUESTION can be empty.
""".strip()


def build_system_prompt(session: Session, objectives: list[str], in_closing_window: bool) -> str:
    objectives_text = "\n".join(f"- {o}" for o in objectives)
    reason_line = (
        f'The clinician already recorded the patient\'s reason for this consultation: '
        f'"{session.consultation_reason}". This is already known — NEVER ask the patient what '
        "their reason for consulting is, what brings them in, or anything equivalent; that "
        "question is already answered. Your very first question must instead go directly "
        "deeper into that stated reason (a detail, a timeframe, an impact it's had)."
        if session.consultation_reason
        else "No consultation reason was given upfront — your first question should establish "
        "what brings the patient in today."
    )
    closing_line = (
        "\nYou are nearly out of time: ask at most one more question, only if there is a "
        "critical gap left, otherwise answer DONE: YES right away."
        if in_closing_window
        else ""
    )

    return f"""
You are conducting a structured pre-visit interview for a {session.specialty} consultation \
({_MODE_DESCRIPTIONS[session.mode]}).

{reason_line}

Your goal is to gather enough information to cover the following, adapting the specific \
questions to the specialty and to what the patient has already said:
{objectives_text}

Ask ONE question at a time. Mark it TYPE: YES_NO whenever it's naturally answerable with just \
yes or no — e.g. "¿Toma alguna medicación actualmente?", "¿Ha tenido este síntoma antes?", \
"¿Ha notado fiebre?" are all YES_NO, even though the topic could be explored further later in \
a separate, follow-up question. Only mark it TYPE: TEXT when the answer itself needs to be a \
description, a number, or a choice from more than two options (a symptom, a timeframe, a scale \
rating, a list of medications). The patient is answering on their phone, so default to YES_NO \
whenever it fits — don't make a question open-ended just because the topic is important.

Each question must ask about exactly ONE thing. Never bundle several sub-questions into one \
(e.g. "what foods do you eat, and has how often you eat them changed?") — the patient answers \
only one part, then feels asked twice when you follow up on the other. Ask them separately, one \
per turn.

Before writing your question, re-read the transcript below. NEVER ask something that is the \
same as, or a paraphrase/rewording of, a question already in the transcript — check every \
previous Q, not just the last one. If the patient's own answer raised something specific and \
relevant (a symptom, a change, a worry) without enough detail, you may follow up on it, but \
the follow-up must be a NEW, more specific question (e.g. ask for a detail, a timeframe, or a \
cause that hasn't been asked yet) — never the same question again, and never just to double-\
check something the patient already answered clearly.
{closing_line}

{_RESPONSE_FORMAT}
""".strip()


def build_user_prompt(previous_answers: list[Answer], elapsed_seconds: float, budget: QuestionnaireBudget) -> str:
    if not previous_answers:
        transcript = "(No questions asked yet — this is the first question.)"
        already_asked = ""
    else:
        transcript = "\n".join(f'Q{a.order}: "{a.question}"\nA{a.order}: "{a.answer}"' for a in previous_answers)
        # a separate numbered blocklist is far more salient to a small model
        # than expecting it to scan the transcript for repeats (see D-025)
        asked_list = "\n".join(f"{a.order}. {a.question}" for a in previous_answers)
        already_asked = (
            "\n\nQuestions ALREADY ASKED — do not ask any of these again, and do not ask anything "
            f"that overlaps with them, even in part:\n{asked_list}"
        )

    remaining = max(0, budget.time_budget_seconds - elapsed_seconds)
    time_note = (
        f"Time elapsed: {int(elapsed_seconds)}s of a {budget.time_budget_seconds}s budget "
        f"({int(remaining)}s remaining)."
    )

    return f"{time_note}\n\nTranscript so far:\n{transcript}{already_asked}\n\nGenerate the next step."
