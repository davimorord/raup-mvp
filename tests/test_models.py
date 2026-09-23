from raup.models import ConsultationMode, Session, SessionStatus


def test_session_uses_default_values():
    session = Session(code="AB12CD", mode=ConsultationMode.FIRST_VISIT)

    assert session.status == SessionStatus.CREATED
    assert session.consultation_reason is None
    assert session.completed_at is None
    assert session.id  # auto-generated
    assert session.created_at is not None


def test_each_session_has_distinct_id():
    a = Session(code="AAAAAA", mode=ConsultationMode.FOLLOW_UP)
    b = Session(code="BBBBBB", mode=ConsultationMode.FOLLOW_UP)

    assert a.id != b.id
