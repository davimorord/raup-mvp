"""Adaptive questionnaire engine.

`get_next_step` is the one entry point raup/ui/patient.py uses: given the
session, the answers so far, and elapsed time, it returns either the next
question to ask or a signal that the interview is done. The time/question
cutoff is enforced here in code, deterministically — never left to the LLM
(see budget.py); the LLM only ever gets to decide "done" *early*, within
that hard boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from raup.llm.base import LLMClient
from raup.llm.safe_client import UnsafeOutputError, generate_safely
from raup.models import Answer, Session
from raup.questionnaire.budget import get_budget, is_in_closing_window, is_over_budget
from raup.questionnaire.objectives import get_objectives
from raup.questionnaire.prompts import build_system_prompt, build_user_prompt
from raup.questionnaire.protocol import parse_response


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
    user_prompt = build_user_prompt(previous_answers, elapsed_seconds, budget)

    try:
        raw_response = generate_safely(llm_client, system_prompt, user_prompt)
    except UnsafeOutputError:
        # the model couldn't produce a safe question after retries (see D-016) —
        # end the interview rather than risk showing anything to the patient
        return QuestionnaireStep(done=True)

    parsed = parse_response(raw_response)

    if parsed.done or not parsed.question:
        return QuestionnaireStep(done=True)

    return QuestionnaireStep(done=False, question=parsed.question, question_type=parsed.question_type)
