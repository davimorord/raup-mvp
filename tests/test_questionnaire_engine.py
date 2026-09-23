from raup.models import Answer, ConsultationMode, Session
from raup.questionnaire.engine import get_next_step
from tests.fakes import FakeLLMClient


def _session(mode=ConsultationMode.FIRST_VISIT) -> Session:
    return Session(code="ABC123", mode=mode, consultation_reason="Dolor lumbar de 3 semanas")


def test_returns_next_question_when_llm_says_not_done():
    client = FakeLLMClient(responses=["QUESTION: ¿Desde cuándo?\nTYPE: TEXT\nDONE: NO"])

    step = get_next_step(client, _session(), previous_answers=[], elapsed_seconds=10)

    assert step.done is False
    assert step.question == "¿Desde cuándo?"
    assert step.question_type == "TEXT"


def test_ends_when_llm_says_done():
    client = FakeLLMClient(responses=["QUESTION:\nTYPE: TEXT\nDONE: YES"])

    step = get_next_step(client, _session(), previous_answers=[], elapsed_seconds=30)

    assert step.done is True


def test_ends_without_calling_llm_once_time_budget_is_exceeded():
    client = FakeLLMClient(responses=[])  # would raise if called — asserts no call happens

    step = get_next_step(client, _session(ConsultationMode.FOLLOW_UP), previous_answers=[], elapsed_seconds=5 * 60)

    assert step.done is True
    assert client.calls == []


def test_ends_once_question_safety_valve_is_hit_even_with_time_left():
    from raup.models import Answer
    from raup.questionnaire.budget import get_budget

    client = FakeLLMClient(responses=[])
    budget = get_budget(ConsultationMode.FOLLOW_UP)
    previous_answers = [
        Answer(session_id="s1", order=i, question=f"Q{i}", answer=f"A{i}") for i in range(budget.max_questions)
    ]

    step = get_next_step(client, _session(ConsultationMode.FOLLOW_UP), previous_answers, elapsed_seconds=10)

    assert step.done is True
    assert client.calls == []


def test_ends_gracefully_if_the_model_can_only_produce_unsafe_output():
    # 3 unsafe responses in a row exhausts generate_safely's retries (see D-016)
    client = FakeLLMClient(responses=["Tienes ansiedad generalizada."] * 3)

    step = get_next_step(client, _session(), previous_answers=[], elapsed_seconds=10)

    assert step.done is True


def test_rejects_a_duplicate_question_and_retries():
    previous_answers = [Answer(session_id="s1", order=1, question="¿Cómo ha sido su adherencia?", answer="Bien")]
    client = FakeLLMClient(
        responses=[
            "QUESTION: ¿Cómo ha sido su adherencia?\nTYPE: TEXT\nDONE: NO",  # duplicate
            "QUESTION: ¿Ha notado cambios en su nivel de energía?\nTYPE: TEXT\nDONE: NO",  # fresh
        ]
    )

    step = get_next_step(client, _session(), previous_answers, elapsed_seconds=30)

    assert step.done is False
    assert step.question == "¿Ha notado cambios en su nivel de energía?"
    assert len(client.calls) == 2


def test_gives_up_and_ends_after_repeated_duplicates_instead_of_showing_one():
    previous_answers = [Answer(session_id="s1", order=1, question="¿Cómo ha sido su adherencia?", answer="Bien")]
    client = FakeLLMClient(
        responses=["QUESTION: ¿Cómo ha sido su adherencia?\nTYPE: TEXT\nDONE: NO"] * 3
    )

    step = get_next_step(client, _session(), previous_answers, elapsed_seconds=30)

    assert step.done is True
    assert len(client.calls) == 3


def test_duplicate_retry_reminder_names_the_repeated_question():
    previous_answers = [Answer(session_id="s1", order=1, question="¿Cómo ha sido su adherencia?", answer="Bien")]
    client = FakeLLMClient(
        responses=[
            "QUESTION: ¿Cómo ha sido su adherencia?\nTYPE: TEXT\nDONE: NO",
            "QUESTION: ¿Algo distinto?\nTYPE: TEXT\nDONE: NO",
        ]
    )

    get_next_step(client, _session(), previous_answers, elapsed_seconds=30)

    _, second_user_prompt = client.calls[1]
    assert "repeats something already asked" in second_user_prompt


def test_passes_consultation_reason_and_specialty_into_the_prompt():
    client = FakeLLMClient(responses=["QUESTION: ¿Algo más?\nTYPE: TEXT\nDONE: NO"])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT, specialty="Fisioterapia", consultation_reason="Dolor de rodilla")

    get_next_step(client, session, previous_answers=[], elapsed_seconds=0)

    system_prompt, _ = client.calls[0]
    assert "Fisioterapia" in system_prompt
    assert "Dolor de rodilla" in system_prompt
