from pathlib import Path

from streamlit.testing.v1 import AppTest

from raup.models import ConsultationMode, Session
from tests.fakes import (
    FakeLLMClient,
    InMemoryAnswerRepository,
    InMemoryReportRepository,
    InMemorySessionRepository,
)

_HARNESS = str(Path(__file__).parent / "apps" / "harness_patient.py")


def test_invalid_code_shows_error():
    at = AppTest.from_file(_HARNESS)
    at.session_state["test_code"] = "NOEXISTE"
    at.run()

    assert not at.exception
    assert any("no es válido" in e.value for e in at.error)


def test_valid_code_marks_session_in_progress_and_shows_first_question():
    repo = InMemorySessionRepository()
    session = repo.create(Session(code="ABCD12", mode=ConsultationMode.FIRST_VISIT))

    at = AppTest.from_file(_HARNESS)
    at.session_state["session_repo"] = repo
    at.session_state["llm_client"] = FakeLLMClient(
        responses=["QUESTION: ¿Cómo se encuentra hoy?\nTYPE: TEXT\nDONE: NO"]
    )
    at.session_state["test_code"] = "ABCD12"
    at.run()

    assert not at.exception
    assert repo.get_by_id(session.id).status.value == "en_curso"
    assert any("Primera consulta" in c.value for c in at.caption)
    assert any("¿Cómo se encuentra hoy?" in s.value for s in at.subheader)


def test_answering_a_text_question_saves_it_and_advances():
    session_repo = InMemorySessionRepository()
    session = session_repo.create(Session(code="TEXTQ1", mode=ConsultationMode.FIRST_VISIT))
    answer_repo = InMemoryAnswerRepository()

    at = AppTest.from_file(_HARNESS)
    at.session_state["session_repo"] = session_repo
    at.session_state["answer_repo"] = answer_repo
    at.session_state["llm_client"] = FakeLLMClient(
        responses=[
            "QUESTION: ¿Cómo se encuentra hoy?\nTYPE: TEXT\nDONE: NO",
            "QUESTION: ¿Desde cuándo?\nTYPE: TEXT\nDONE: NO",
        ]
    )
    at.session_state["test_code"] = "TEXTQ1"
    at.run()

    at.text_area[0].set_value("Con dolor lumbar")
    at.button[0].click().run()

    assert not at.exception
    saved = answer_repo.list_by_session(session.id)
    assert len(saved) == 1
    assert saved[0].answer == "Con dolor lumbar"
    assert any("¿Desde cuándo?" in s.value for s in at.subheader)


def test_answering_a_yes_no_question_via_button():
    session_repo = InMemorySessionRepository()
    session = session_repo.create(Session(code="YESNO1", mode=ConsultationMode.FIRST_VISIT))
    answer_repo = InMemoryAnswerRepository()

    at = AppTest.from_file(_HARNESS)
    at.session_state["session_repo"] = session_repo
    at.session_state["answer_repo"] = answer_repo
    at.session_state["llm_client"] = FakeLLMClient(
        responses=[
            "QUESTION: ¿Ha tomado alguna medicación?\nTYPE: YES_NO\nDONE: NO",
            "QUESTION: ¿Cuál?\nTYPE: TEXT\nDONE: NO",
        ]
    )
    at.session_state["test_code"] = "YESNO1"
    at.run()

    assert any("¿Ha tomado alguna medicación?" in s.value for s in at.subheader)
    at.button[0].click().run()  # "Sí"

    assert not at.exception
    saved = answer_repo.list_by_session(session.id)
    assert len(saved) == 1
    assert saved[0].answer == "Sí"
    assert any("¿Cuál?" in s.value for s in at.subheader)


def test_reaching_done_marks_session_completed_and_generates_report():
    session_repo = InMemorySessionRepository()
    session = session_repo.create(Session(code="DONE01", mode=ConsultationMode.FOLLOW_UP))
    report_repo = InMemoryReportRepository()

    at = AppTest.from_file(_HARNESS)
    at.session_state["session_repo"] = session_repo
    at.session_state["report_repo"] = report_repo
    at.session_state["llm_client"] = FakeLLMClient(
        responses=[
            "QUESTION:\nTYPE: TEXT\nDONE: YES",  # questionnaire step: done
            "WEIGHT_LOSS_KG: UNKNOWN\nWEIGHT_BEFORE_KG: UNKNOWN\nWEIGHT_LOSS_PERIOD_MONTHS: UNKNOWN\n"
            "SELF_INDUCED_VOMITING: UNKNOWN\nLOSS_OF_CONTROL_EATING: UNKNOWN\n"
            "BODY_IMAGE_DISTORTION: UNKNOWN\nFOOD_PREOCCUPATION: UNKNOWN",  # extraction
            "El paciente refiere seguimiento sin incidencias.",  # executive summary
            "- Ninguna área adicional a destacar.",  # areas to explore
        ]
    )
    at.session_state["test_code"] = "DONE01"
    at.run()

    assert not at.exception
    assert session_repo.get_by_id(session.id).status.value == "completada"
    assert any("Gracias" in m.value for m in at.success)

    report = report_repo.get_by_session(session.id)
    assert report is not None
    assert report.executive_summary == "El paciente refiere seguimiento sin incidencias."


def test_report_generation_failure_does_not_break_the_thank_you_screen():
    session_repo = InMemorySessionRepository()
    session_repo.create(Session(code="FAIL01", mode=ConsultationMode.FOLLOW_UP))
    report_repo = InMemoryReportRepository()

    at = AppTest.from_file(_HARNESS)
    at.session_state["session_repo"] = session_repo
    at.session_state["report_repo"] = report_repo
    # only one scripted response — extraction's own call runs out of responses
    at.session_state["llm_client"] = FakeLLMClient(responses=["QUESTION:\nTYPE: TEXT\nDONE: YES"])
    at.session_state["test_code"] = "FAIL01"
    at.run()

    assert not at.exception
    assert any("Gracias" in m.value for m in at.success)
