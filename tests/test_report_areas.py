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
    topics = ["sueño", "estrés laboral", "actividad física", "consumo de alcohol", "horarios de comida",
              "hidratación diaria", "antecedentes familiares", "tabaquismo"]
    client = FakeLLMClient(responses=["\n".join(f"- Profundizar en {t}" for t in topics)])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT)

    areas = generate_areas_to_explore(client, session, answers=[])

    assert len(areas) == 5


def test_repeated_areas_and_already_asked_questions_are_dropped():
    # the real degenerate output (D-026): 4 of 5 identical, re-asking Q3
    from raup.models import Answer

    asked = "¿Podría describir con más detalle qué tipo de alimentos suelen desencadenar o empeorar sus síntomas de reflujo?"
    raw = "\n".join([
        f"- {asked}",
        "- ¿Ha notado algún cambio en su nivel de estrés en los últimos meses?",
        f"- {asked}",
        f"- {asked}",
        f"- {asked}",
    ])
    client = FakeLLMClient(responses=[raw])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT)
    answers = [Answer(session_id=session.id, order=1, question=asked, answer="Hamburguesas, embutidos")]

    areas = generate_areas_to_explore(client, session, answers)

    assert areas == ["¿Ha notado algún cambio en su nivel de estrés en los últimos meses?"]


def test_a_question_cut_off_mid_sentence_is_dropped():
    # live run (D-026): the last area came back as just "¿Podría describir"
    client = FakeLLMClient(responses=["- ¿Ha notado cambios en su sueño?\n- ¿Podría describir"])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT)

    areas = generate_areas_to_explore(client, session, answers=[])

    assert areas == ["¿Ha notado cambios en su sueño?"]


def test_empty_response_yields_empty_list():
    client = FakeLLMClient(responses=["no bullet points here at all"])
    session = Session(code="ABC123", mode=ConsultationMode.FIRST_VISIT)

    areas = generate_areas_to_explore(client, session, answers=[])

    assert areas == []
