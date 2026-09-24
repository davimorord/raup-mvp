"""Adaptive questionnaire engine.

`get_next_step` is the one entry point raup/ui/patient.py uses: given the
session, the answers so far, and elapsed time, it returns either the next
question to ask or a signal that the interview is done. Every stopping and
repetition rule is enforced here in code, never left to the LLM:

- time/question budget, a hard cutoff checked before any LLM call (budget.py)
- repeated questions, rejected and retried (dedup.py, D-024/D-025)
- mandatory topics, which the LLM can't skip by declaring itself done early
  (coverage.py, D-026)

The LLM only ever decides *which* question to ask, within those bounds.
"""

from __future__ import annotations

from dataclasses import dataclass

from raup.llm.base import LLMClient
from raup.llm.safe_client import UnsafeOutputError, generate_safely
from raup.models import Answer, Session
from raup.questionnaire.budget import get_budget, is_in_closing_window, is_over_budget
from raup.questionnaire.coverage import get_mandatory_topics, next_required_question
from raup.questionnaire.dedup import is_duplicate_question
from raup.questionnaire.objectives import get_objectives
from raup.questionnaire.prompts import build_system_prompt, build_user_prompt
from raup.questionnaire.protocol import parse_response

_MAX_DUPLICATE_RETRIES = 2


@dataclass(frozen=True)
class QuestionnaireStep:
    done: bool
    question: str = ""
    question_type: str = "TEXT"


def _fixed_step(required: tuple[str, str]) -> QuestionnaireStep:
    question, question_type = required
    return QuestionnaireStep(done=False, question=question, question_type=question_type)


def get_next_step(
    llm_client: LLMClient, session: Session, previous_answers: list[Answer], elapsed_seconds: float
) -> QuestionnaireStep:
    # hard, deterministic cutoff — checked before ever calling the LLM. Time
    # is the maximum (D-020): uncovered mandatory topics then surface in the
    # report's "areas to explore" instead of extending the interview.
    if is_over_budget(session.mode, elapsed_seconds, len(previous_answers)):
        return QuestionnaireStep(done=True)

    required = next_required_question(session, previous_answers)
    in_closing_window = is_in_closing_window(session.mode, elapsed_seconds)

    # last minute: mandatory topics take priority over whatever the model
    # would ask — no LLM call needed
    if in_closing_window and required:
        return _fixed_step(required)

    step = _ask_llm(llm_client, session, previous_answers, elapsed_seconds, in_closing_window)

    # the model can't end the interview early while a mandatory topic is
    # uncovered, or only ever got a bare "Sí" (D-026)
    if step.done and required:
        return _fixed_step(required)
    return step


def _ask_llm(
    llm_client: LLMClient,
    session: Session,
    previous_answers: list[Answer],
    elapsed_seconds: float,
    in_closing_window: bool,
) -> QuestionnaireStep:
    budget = get_budget(session.mode)
    system_prompt = build_system_prompt(
        session,
        get_objectives(session.mode),
        in_closing_window,
        mandatory_topics=[t.prompt_description for t in get_mandatory_topics(session)],
    )
    base_user_prompt = build_user_prompt(previous_answers, elapsed_seconds, budget)
    user_prompt = base_user_prompt

    for _ in range(_MAX_DUPLICATE_RETRIES + 1):
        try:
            raw_response = generate_safely(llm_client, system_prompt, user_prompt)
        except UnsafeOutputError:
            # the model couldn't produce a safe question after retries (see
            # D-016) — stop asking it; get_next_step may still add a fixed
            # mandatory question, which is static and safe
            return QuestionnaireStep(done=True)

        parsed = parse_response(raw_response)

        if parsed.done or not parsed.question:
            return QuestionnaireStep(done=True)

        if not is_duplicate_question(parsed.question, previous_answers):
            return QuestionnaireStep(done=False, question=parsed.question, question_type=parsed.question_type)

        # duplicate (see D-024) — retry with an explicit reminder of what to
        # avoid, rather than ever showing the patient a repeated question
        user_prompt = (
            f'{base_user_prompt}\n\nYou just generated "{parsed.question}", which repeats something '
            "already asked (see the transcript above) — do not ask it again, even paraphrased. Ask "
            "about a different, unexplored angle, or answer DONE: YES if nothing meaningfully new is left."
        )

    # exhausted retries without a fresh question
    return QuestionnaireStep(done=True)
