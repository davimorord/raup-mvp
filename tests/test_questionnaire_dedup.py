from raup.models import Answer
from raup.questionnaire.dedup import is_duplicate_question


def _answer(question: str) -> Answer:
    return Answer(session_id="s1", order=1, question=question, answer="algo")


def test_exact_repeat_is_a_duplicate():
    previous = [_answer("¿Ha notado alguna diferencia en su peso desde la última consulta?")]
    assert is_duplicate_question("¿Ha notado alguna diferencia en su peso desde la última consulta?", previous)


def test_near_paraphrase_is_a_duplicate():
    previous = [_answer("¿Ha notado alguna diferencia en su apetito o en la frecuencia con la que come?")]
    assert is_duplicate_question(
        "¿Ha notado alguna diferencia en su apetito o en la frecuencia con la que come desde la última consulta?",
        previous,
    )


def test_case_and_punctuation_do_not_matter():
    previous = [_answer("¿Cómo describiría el dolor, en una escala del 1 al 10?")]
    assert is_duplicate_question("como describiria el dolor en una escala del 1 al 10", previous)


def test_a_genuinely_different_question_is_not_a_duplicate():
    previous = [_answer("¿Cómo ha sido su adherencia al plan acordado?")]
    assert not is_duplicate_question("¿Ha notado cambios en su nivel de energía?", previous)


def test_empty_previous_answers_means_no_duplicate():
    assert not is_duplicate_question("¿Cómo se encuentra hoy?", [])


def test_checks_against_every_previous_question_not_just_the_last():
    previous = [
        _answer("¿Cómo ha sido su adherencia al plan acordado?"),
        _answer("¿Ha notado cambios en su nivel de energía?"),
        _answer("¿Cómo describiría el dolor en una escala del 1 al 10?"),
    ]
    assert is_duplicate_question("¿Cómo ha sido su adherencia al plan que se acordó?", previous)
