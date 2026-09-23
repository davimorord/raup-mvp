"""Contract tests for the repositories, run against the in-memory doubles
(tests/fakes.py). If real integration tests against Supabase are ever
needed, they should reuse these same assertions against
`raup.repository.supabase_repo`.
"""

import pytest

from raup.models import (
    Alert,
    ConsultationMode,
    DocumentMetadata,
    Answer,
    Report,
    Session,
    SessionStatus,
)
from tests.fakes import (
    InMemoryAnswerRepository,
    InMemoryDocumentRepository,
    InMemoryReportRepository,
    InMemorySessionRepository,
)


def test_create_and_get_session_by_code():
    repo = InMemorySessionRepository()
    session = Session(code="7K9XQP", mode=ConsultationMode.FIRST_VISIT, consultation_reason="Dolor lumbar")

    repo.create(session)

    found = repo.get_by_code("7K9XQP")
    assert found is not None
    assert found.id == session.id
    assert found.consultation_reason == "Dolor lumbar"


def test_get_by_nonexistent_code_returns_none():
    repo = InMemorySessionRepository()
    assert repo.get_by_code("NOEXISTE") is None


def test_does_not_allow_duplicate_codes():
    repo = InMemorySessionRepository()
    repo.create(Session(code="DUPLICA", mode=ConsultationMode.FOLLOW_UP))

    with pytest.raises(ValueError):
        repo.create(Session(code="DUPLICA", mode=ConsultationMode.FOLLOW_UP))


def test_update_status():
    repo = InMemorySessionRepository()
    session = Session(code="ESTADO1", mode=ConsultationMode.FOLLOW_UP)
    repo.create(session)

    repo.update_status(session.id, SessionStatus.COMPLETED)

    assert repo.get_by_id(session.id).status == SessionStatus.COMPLETED


def test_answers_are_listed_in_order():
    repo = InMemoryAnswerRepository()
    repo.add(Answer(session_id="s1", order=2, question="¿Cómo duerme?", answer="Mal"))
    repo.add(Answer(session_id="s1", order=1, question="¿Motivo?", answer="Seguimiento"))

    answers = repo.list_by_session("s1")

    assert [a.order for a in answers] == [1, 2]


def test_documents_by_session():
    repo = InMemoryDocumentRepository()
    repo.add_metadata(
        DocumentMetadata(
            session_id="s1",
            file_name="analitica.pdf",
            storage_path="s1/analitica.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
        )
    )

    documents = repo.list_by_session("s1")

    assert len(documents) == 1
    assert documents[0].file_name == "analitica.pdf"


def test_report_is_saved_and_retrieved_by_session():
    repo = InMemoryReportRepository()
    report = Report(
        session_id="s1",
        executive_summary="El paciente refiere dolor lumbar de 3 semanas de evolución.",
        alerts=[Alert(code="DOLOR_ALTO", message="Dolor referido 8/10", source="Escala numérica de dolor")],
        areas_to_explore=["Profundizar en el patrón de sueño"],
    )

    repo.save(report)

    retrieved = repo.get_by_session("s1")
    assert retrieved is not None
    assert retrieved.executive_summary == report.executive_summary
    assert len(retrieved.alerts) == 1


def test_nonexistent_report_returns_none():
    repo = InMemoryReportRepository()
    assert repo.get_by_session("no-existe") is None
