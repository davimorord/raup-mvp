from raup.models import Answer, ConsultationMode, Session
from raup.questionnaire.budget import get_budget
from raup.questionnaire.objectives import get_objectives
from raup.questionnaire.prompts import build_system_prompt, build_user_prompt


def _session(reason="Bajada de peso para una boda en 4 meses.") -> Session:
    return Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT, specialty="Nutrición", consultation_reason=reason)


def _system_prompt(session: Session) -> str:
    return build_system_prompt(session, get_objectives(session.mode), in_closing_window=False)


def test_known_reason_is_never_asked_again():
    prompt = _system_prompt(_session())
    assert "Bajada de peso para una boda" in prompt
    assert "NEVER ask the patient what their reason for consulting is" in prompt


def test_missing_reason_asks_for_it_instead():
    prompt = _system_prompt(_session(reason=None))
    assert "No consultation reason was given upfront" in prompt
    assert "NEVER ask the patient what their reason" not in prompt


def test_yes_no_guidance_names_the_medication_question_as_yes_no():
    assert "¿Toma alguna medicación actualmente?" in _system_prompt(_session())


def test_bundled_questions_are_forbidden():
    assert "exactly ONE thing" in _system_prompt(_session())


def test_user_prompt_lists_already_asked_questions_separately_from_the_transcript():
    answers = [
        Answer(session_id="s1", order=1, question="¿Cómo se encuentra hoy?", answer="Bien"),
        Answer(session_id="s1", order=2, question="¿Desde cuándo?", answer="Hace un mes"),
    ]
    prompt = build_user_prompt(answers, elapsed_seconds=30, budget=get_budget(ConsultationMode.FIRST_VISIT))

    assert "Questions ALREADY ASKED" in prompt
    assert "1. ¿Cómo se encuentra hoy?" in prompt
    assert "2. ¿Desde cuándo?" in prompt


def test_user_prompt_has_no_already_asked_block_before_the_first_question():
    prompt = build_user_prompt([], elapsed_seconds=0, budget=get_budget(ConsultationMode.FIRST_VISIT))
    assert "ALREADY ASKED" not in prompt
