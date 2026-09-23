"""Adaptive questionnaire engine.

`get_next_step` is the one entry point raup/ui/patient.py uses: given the
session, the answers so far, and elapsed time, it returns either the next
question to ask or a signal that the interview is done. The time/question
cutoff is enforced here in code, deterministically — never left to the LLM
(see budget.py); the LLM only ever gets to decide "done" *early*, within
that hard boundary. Repeated questions are also caught and rejected here
(see dedup.py, D-024) rather than trusted to the model's own instructions.
"""

from __future__ import annotations

from dataclasses import dataclass

from raup.llm.base import LLMClient
from raup.llm.safe_client import UnsafeOutputError, generate_safely
from raup.models import Answer, Session
from raup.questionnaire.budget import get_budget, is_in_closing_window, is_over_budget
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


def get_next_step(
    llm_client: LLMClient, session: Session, previous_answers: list[Answer], elapsed_seconds: float
) -> QuestionnaireStep:
    questions_asked = len(previous_answers)

    # hard, deterministic cutoff — checked before ever calling the LLM
    if is_over_budget(session.mode, elapsed_seconds, questions_asked):
        return QuestionnaireStep(done=True)

    budget = get_budget(session.mode)
    objectives = get_objectives(session.mode)
    in_closing_window = is_in_closing_window(session.mode, elapsed_seconds)
    system_prompt = build_system_prompt(session, objectives, in_closing_window)
    base_user_prompt = build_user_prompt(previous_answers, elapsed_seconds, budget)
    user_prompt = base_user_prompt

    for attempt in range(_MAX_DUPLICATE_RETRIES + 1):
        try:
            raw_response = generate_safely(llm_client, system_prompt, user_prompt)
        except UnsafeOutputError:
            # the model couldn't produce a safe question after retries (see
            # D-016) — end the interview rather than risk showing anything
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

    # exhausted retries without a fresh question — end gracefully rather
    # than show the patient a repeated question
    return QuestionnaireStep(done=True)
