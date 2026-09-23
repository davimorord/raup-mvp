from raup.models import ConsultationMode, Session
from raup.report.engine import generate_report
from tests.fakes import FakeLLMClient

_EXTRACTION_RESPONSE = (
    "WEIGHT_LOSS_KG: 12\nWEIGHT_BEFORE_KG: 100\nWEIGHT_LOSS_PERIOD_MONTHS: 3\n"
    "SELF_INDUCED_VOMITING: NO\nLOSS_OF_CONTROL_EATING: NO\n"
    "BODY_IMAGE_DISTORTION: NO\nFOOD_PREOCCUPATION: NO"
)


def test_generate_report_produces_summary_alerts_and_areas():
    client = FakeLLMClient(
        responses=[
            _EXTRACTION_RESPONSE,
            "El paciente refiere pérdida de peso no intencionada del 12% en 3 meses.",
            "- Profundizar en el patrón de sueño\n- Profundizar en la actividad física habitual",
        ]
    )
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT, specialty="Nutrición")

    report = generate_report(client, session, answers=[])

    assert report.session_id == session.id
    assert "12%" in report.executive_summary
    assert len(report.alerts) == 1
    assert report.alerts[0].code == "MUST_ALTO"
    assert report.areas_to_explore == [
        "Profundizar en el patrón de sueño",
        "Profundizar en la actividad física habitual",
    ]


def test_generate_report_has_no_alerts_for_non_nutrition_specialty():
    client = FakeLLMClient(
        responses=[
            _EXTRACTION_RESPONSE,
            "El paciente refiere dolor de rodilla.",
            "- Ninguna área adicional a destacar.",
        ]
    )
    session = Session(code="ABC124", mode=ConsultationMode.FIRST_VISIT, specialty="Fisioterapia")

    report = generate_report(client, session, answers=[])

    assert report.alerts == []
