from raup.models import Answer
from raup.questionnaire.dedup import is_duplicate_question

_TEMPLATE = "¿Ha notado alguna diferencia en su {} desde la última consulta?"


def _answers(*questions: str) -> list[Answer]:
    return [Answer(session_id="s1", order=i + 1, question=q, answer="algo") for i, q in enumerate(questions)]


# --- must be flagged: real repeats seen in live tests (D-024, D-025) ---------------------------


def test_exact_repeat_is_a_duplicate():
    assert is_duplicate_question(_TEMPLATE.format("peso"), _answers(_TEMPLATE.format("peso")))


def test_near_paraphrase_is_a_duplicate():
    previous = _answers("¿Ha notado alguna diferencia en su apetito o en la frecuencia con la que come?")
    assert is_duplicate_question(
        "¿Ha notado algún cambio en su apetito o en la frecuencia con la que come desde la última consulta?",
        previous,
    )


def test_case_and_punctuation_do_not_matter():
    previous = _answers("¿Cómo describiría el dolor, en una escala del 1 al 10?")
    assert is_duplicate_question("como describiria el dolor en una escala del 1 al 10", previous)


def test_short_follow_up_that_re_asks_part_of_a_longer_compound_question_is_a_duplicate():
    # the real "ya te he respondido antes" case: string similarity was 0.72, under the 0.75 threshold
    previous = _answers(
        "¿Podría describir qué tipo de alimentos suele comer en casa, fuera de casa, y si ha notado "
        "alguna diferencia en la frecuencia con la que come estos alimentos en los últimos meses?"
    )
    assert is_duplicate_question(
        "¿Podría indicar si ha notado algún cambio en la frecuencia con la que come estos alimentos "
        "en los últimos meses?",
        previous,
    )


def test_checks_against_every_previous_question_not_just_the_last():
    previous = _answers(_TEMPLATE.format("peso"), _TEMPLATE.format("energía"), _TEMPLATE.format("sueño"))
    assert is_duplicate_question(_TEMPLATE.format("peso"), previous)


# --- must NOT be flagged: legitimate questions that merely look alike -----------------------------


def test_same_template_with_a_different_topic_is_not_a_duplicate():
    # common in follow-up interviews; flagging these could end the interview early
    previous = _answers(_TEMPLATE.format("peso"))
    assert not is_duplicate_question(_TEMPLATE.format("apetito"), previous)
    assert not is_duplicate_question(_TEMPLATE.format("sueño"), _answers(_TEMPLATE.format("peso"), _TEMPLATE.format("apetito")))


def test_a_different_angle_on_the_same_topic_is_not_a_duplicate():
    previous = _answers("¿En una escala del 1 al 10, cómo describiría el dolor de su hernia discal?")
    assert not is_duplicate_question("¿Desde cuándo tiene el dolor de la hernia discal?", previous)
    assert not is_duplicate_question("¿Qué actividades le agravan el dolor de la hernia discal?", previous)


def test_a_genuinely_different_question_is_not_a_duplicate():
    previous = _answers("¿Cómo ha sido su adherencia al plan acordado?")
    assert not is_duplicate_question("¿Ha notado cambios en su nivel de energía?", previous)


def test_empty_previous_answers_means_no_duplicate():
    assert not is_duplicate_question("¿Cómo se encuentra hoy?", [])
