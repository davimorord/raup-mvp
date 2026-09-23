"""Time and question budgets for the adaptive questionnaire.

Time is the real constraint (matches CLAUDE.md's scope: 5-7 min first visit,
3-5 min follow-up), enforced as a hard, deterministic cutoff in code — never
left to the LLM's own judgment of "how long has this taken." The question
count is only a secondary safety valve: generous enough that it should
essentially never bind in normal use, there purely to stop a pathological
non-terminating interview (the model never signaling completion) regardless
of the clock.
"""

from __future__ import annotations

from dataclasses import dataclass

from raup.models import ConsultationMode


@dataclass(frozen=True)
class QuestionnaireBudget:
    time_budget_seconds: int
    closing_window_seconds: int
    max_questions: int


_BUDGETS = {
    ConsultationMode.FIRST_VISIT: QuestionnaireBudget(
        time_budget_seconds=7 * 60,
        closing_window_seconds=60,
        max_questions=15,
    ),
    ConsultationMode.FOLLOW_UP: QuestionnaireBudget(
        time_budget_seconds=5 * 60,
        closing_window_seconds=60,
        max_questions=10,
    ),
}


def get_budget(mode: ConsultationMode) -> QuestionnaireBudget:
    return _BUDGETS[mode]


def is_over_budget(mode: ConsultationMode, elapsed_seconds: float, questions_asked: int) -> bool:
    budget = get_budget(mode)
    return elapsed_seconds >= budget.time_budget_seconds or questions_asked >= budget.max_questions


def is_in_closing_window(mode: ConsultationMode, elapsed_seconds: float) -> bool:
    budget = get_budget(mode)
    remaining = budget.time_budget_seconds - elapsed_seconds
    return 0 < remaining <= budget.closing_window_seconds
