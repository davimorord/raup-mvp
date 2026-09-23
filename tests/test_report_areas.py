from raup.models import ConsultationMode, Session
from raup.report.areas import generate_areas_to_explore
from tests.fakes import FakeLLMClient


def test_parses_multiple_bullet_lines():
    client = FakeLLMClient(responses=["- Primera área\n- Segunda área\nTexto que no empieza por guion"])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT)

    areas = generate_areas_to_explore(client, session, answers=[])

    assert areas == ["Primera área", "Segunda área"]


def test_no_areas_line_is_kept_as_is():
    client = FakeLLMClient(responses=["- Ninguna área adicional a destacar."])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT)

    areas = generate_areas_to_explore(client, session, answers=[])

    assert areas == ["Ninguna área adicional a destacar."]


def test_output_is_capped_at_five_even_if_the_model_lists_more():
    many_lines = "\n".join(f"- Área {i}" for i in range(20))
    client = FakeLLMClient(responses=[many_lines])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT)

    areas = generate_areas_to_explore(client, session, answers=[])

    assert len(areas) == 5


def test_empty_response_yields_empty_list():
    client = FakeLLMClient(responses=["no bullet points here at all"])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT)

    areas = generate_areas_to_explore(client, session, answers=[])

    assert areas == []
