from raup.models import ConsultationMode
from raup.questionnaire.budget import get_budget, is_in_closing_window, is_over_budget


def test_first_visit_budget_is_seven_minutes():
    budget = get_budget(ConsultationMode.FIRST_VISIT)
    assert budget.time_budget_seconds == 7 * 60


def test_follow_up_budget_is_five_minutes():
    budget = get_budget(ConsultationMode.FOLLOW_UP)
    assert budget.time_budget_seconds == 5 * 60


def test_not_over_budget_within_time_and_question_limits():
    assert not is_over_budget(ConsultationMode.FIRST_VISIT, elapsed_seconds=60, questions_asked=3)


def test_over_budget_once_time_elapses():
    assert is_over_budget(ConsultationMode.FIRST_VISIT, elapsed_seconds=7 * 60, questions_asked=1)


def test_over_budget_once_question_safety_valve_hits_even_if_time_remains():
    budget = get_budget(ConsultationMode.FOLLOW_UP)
    assert is_over_budget(ConsultationMode.FOLLOW_UP, elapsed_seconds=10, questions_asked=budget.max_questions)


def test_closing_window_triggers_in_final_minute():
    assert is_in_closing_window(ConsultationMode.FIRST_VISIT, elapsed_seconds=7 * 60 - 30)


def test_closing_window_does_not_trigger_earlier():
    assert not is_in_closing_window(ConsultationMode.FIRST_VISIT, elapsed_seconds=60)


def test_closing_window_does_not_trigger_after_time_is_up():
    # once over budget it's is_over_budget's job, not the closing window
    assert not is_in_closing_window(ConsultationMode.FIRST_VISIT, elapsed_seconds=7 * 60 + 5)
