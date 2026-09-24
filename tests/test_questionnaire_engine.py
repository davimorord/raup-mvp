from raup.models import Answer, ConsultationMode, Session
from raup.questionnaire.coverage import get_mandatory_topics
from raup.questionnaire.engine import get_next_step
from tests.fakes import FakeLLMClient


def _session(mode=ConsultationMode.FIRST_VISIT) -> Session:
    return Session(code="ABC123", mode=mode, consultation_reason="Dolor lumbar de 3 semanas")


def _covering_answers(session: Session) -> list[Answer]:
    """Answers that cover every mandatory topic (D-026), so a test can check
    DONE behavior on its own without the coverage check stepping in."""
    return [
        Answer(session_id=session.id, order=i + 1, question=t.fallback_question, answer="No")
        for i, t in enumerate(get_mandatory_topics(session))
    ]


_FALLBACK_QUESTIONS = {t.fallback_question for t in get_mandatory_topics(_session())}


def test_returns_next_question_when_llm_says_not_done():
    client = FakeLLMClient(responses=["QUESTION: ¿Desde cuándo?\nTYPE: TEXT\nDONE: NO"])

    step = get_next_step(client, _session(), previous_answers=[], elapsed_seconds=10)

    assert step.done is False
    assert step.question == "¿Desde cuándo?"
    assert step.question_type == "TEXT"


def test_ends_when_llm_says_done_and_mandatory_topics_are_covered():
    session = _session()
    client = FakeLLMClient(responses=["QUESTION:\nTYPE: TEXT\nDONE: YES"])

    step = get_next_step(client, session, _covering_answers(session), elapsed_seconds=30)

    assert step.done is True


def test_llm_cannot_end_early_while_a_mandatory_topic_is_missing():
    # the real case (D-026): DONE after 46 s without asking about medication
    client = FakeLLMClient(responses=["QUESTION:\nTYPE: TEXT\nDONE: YES"])

    step = get_next_step(client, _session(), previous_answers=[], elapsed_seconds=46)

    assert step.done is False
    assert step.question == "¿Toma actualmente alguna medicación o suplemento?"
    assert step.question_type == "YES_NO"


def test_mandatory_topics_are_asked_one_at_a_time_until_covered():
    session = _session()
    answers: list[Answer] = []
    asked = []
    for _ in range(10):
        client = FakeLLMClient(responses=["QUESTION:\nTYPE: TEXT\nDONE: YES"])
        step = get_next_step(client, session, answers, elapsed_seconds=60)
        if step.done:
            break
        asked.append(step.question)
        answers.append(Answer(session_id=session.id, order=len(answers) + 1, question=step.question, answer="No"))

    assert asked == [t.fallback_question for t in get_mandatory_topics(session)]
    assert len(asked) == len(set(asked))  # never the same fallback twice


def test_last_minute_asks_a_missing_mandatory_topic_without_calling_the_llm():
    client = FakeLLMClient(responses=[])  # would raise if called

    step = get_next_step(client, _session(), previous_answers=[], elapsed_seconds=7 * 60 - 30)

    assert step.question in _FALLBACK_QUESTIONS
    assert client.calls == []


def test_time_budget_still_wins_over_missing_mandatory_topics():
    # time is the maximum (D-020): uncovered topics go to "areas to explore"
    client = FakeLLMClient(responses=[])

    step = get_next_step(client, _session(), previous_answers=[], elapsed_seconds=7 * 60)

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


def test_unsafe_output_is_never_shown_and_falls_back_to_a_fixed_question():
    # 3 unsafe responses in a row exhausts generate_safely's retries (see D-016)
    client = FakeLLMClient(responses=["Tienes ansiedad generalizada."] * 3)

    step = get_next_step(client, _session(), previous_answers=[], elapsed_seconds=10)

    assert step.question in _FALLBACK_QUESTIONS


def test_ends_gracefully_on_unsafe_output_once_mandatory_topics_are_covered():
    session = _session()
    client = FakeLLMClient(responses=["Tienes ansiedad generalizada."] * 3)

    step = get_next_step(client, session, _covering_answers(session), elapsed_seconds=10)

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


def test_gives_up_after_repeated_duplicates_instead_of_showing_one():
    session = _session()
    repeated = "¿Cómo ha sido su adherencia?"
    previous_answers = _covering_answers(session) + [
        Answer(session_id=session.id, order=99, question=repeated, answer="Bien")
    ]
    client = FakeLLMClient(responses=[f"QUESTION: {repeated}\nTYPE: TEXT\nDONE: NO"] * 3)

    step = get_next_step(client, session, previous_answers, elapsed_seconds=30)

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
