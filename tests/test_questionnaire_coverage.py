import pytest

from raup.llm.guardrails import check_output
from raup.models import Answer, ConsultationMode, Session
from raup.questionnaire.coverage import get_mandatory_topics, get_missing_topics, next_required_question


def _session(mode=ConsultationMode.FIRST_VISIT, specialty="Nutrición") -> Session:
    return Session(code="ABC123", mode=mode, specialty=specialty)


def _answers(*pairs: tuple[str, str]) -> list[Answer]:
    return [Answer(session_id="s1", order=i + 1, question=q, answer=a) for i, (q, a) in enumerate(pairs)]


def _keys(topics) -> list[str]:
    return [t.key for t in topics]


# --- which topics are mandatory: layered by mode and specialty -------------------------------


def test_nutrition_first_visit_has_core_plus_nutrition_topics():
    assert _keys(get_mandatory_topics(_session())) == [
        "medication", "antecedents", "onset", "food_allergies", "weight_changes",
    ]


def test_non_nutrition_first_visit_has_only_the_core_no_food_allergies():
    keys = _keys(get_mandatory_topics(_session(specialty="Fisioterapia")))
    assert keys == ["medication", "antecedents", "onset"]
    assert "food_allergies" not in keys


def test_follow_up_does_not_re_ask_antecedents_or_onset():
    keys = _keys(get_mandatory_topics(_session(mode=ConsultationMode.FOLLOW_UP)))
    assert keys == ["medication_changes", "weight_changes"]


def test_non_nutrition_follow_up_only_asks_about_medication_changes():
    keys = _keys(get_mandatory_topics(_session(mode=ConsultationMode.FOLLOW_UP, specialty="Psicología")))
    assert keys == ["medication_changes"]


# --- what counts as covered ----------------------------------------------------------------


def test_nothing_is_covered_before_any_question():
    assert len(get_missing_topics(_session(), [])) == 5


def test_topic_asked_about_is_covered():
    answers = _answers(("¿Toma alguna medicación actualmente?", "No"))
    assert "medication" not in _keys(get_missing_topics(_session(), answers))


def test_topic_volunteered_by_the_patient_in_an_answer_is_covered():
    # the real reflux case: antacids came up in the patient's own words
    answers = _answers(("¿Cómo ha evolucionado?", "Incluso con el tratamiento de antiácidos no mejoro"))
    assert "medication" not in _keys(get_missing_topics(_session(), answers))


def test_mentioning_a_doctor_does_not_count_as_covering_medication():
    # "médico" must not match the medication keywords
    answers = _answers(("¿Cómo empezó todo?", "Fui al médico hace un año"))
    assert "medication" in _keys(get_missing_topics(_session(), answers))


def test_accents_do_not_matter():
    answers = _answers(("¿Desde cuándo tiene el reflujo?", "Desde los 17 años"))
    assert "onset" not in _keys(get_missing_topics(_session(), answers))


def test_everything_covered_leaves_nothing_missing():
    answers = _answers(
        ("¿Toma alguna medicación?", "No"),
        ("¿Tiene alguna enfermedad diagnosticada?", "No"),
        ("¿Desde cuándo tiene el problema?", "Hace un año"),
        ("¿Tiene alguna alergia alimentaria?", "No"),
        ("¿Ha cambiado su peso?", "Sí, 3 kilos"),
    )
    assert get_missing_topics(_session(), answers) == []


# --- a bare "Sí" needs detail --------------------------------------------------------------

_ALL_COVERED_WITH_NO = (
    ("¿Toma alguna medicación?", "No"),
    ("¿Le han diagnosticado alguna enfermedad?", "No"),
    ("¿Desde cuándo tiene el problema?", "Hace un año"),
    ("¿Tiene alguna alergia alimentaria?", "No"),
    ("¿Ha cambiado su peso?", "No"),
)


def _replace(pairs, index, answer):
    pairs = list(pairs)
    pairs[index] = (pairs[index][0], answer)
    return _answers(*pairs)


def test_everything_answered_no_needs_nothing_more():
    assert next_required_question(_session(), _answers(*_ALL_COVERED_WITH_NO)) is None


def test_bare_yes_to_medication_asks_which_one():
    # the real case (D-026): "Sí" to medication, and nobody asked which
    question, question_type = next_required_question(_session(), _replace(_ALL_COVERED_WITH_NO, 0, "Sí"))
    assert question == "¿Qué medicación o suplementos toma, y con qué frecuencia?"
    assert question_type == "TEXT"


def test_bare_yes_to_weight_asks_for_what_the_must_alert_needs():
    question, _ = next_required_question(_session(), _replace(_ALL_COVERED_WITH_NO, 4, "Sí."))
    assert "kilos" in question and "cuánto pesaba antes" in question


def test_yes_with_detail_needs_no_follow_up():
    answers = _replace(_ALL_COVERED_WITH_NO, 0, "Sí, carbonato cálcico a diario")
    assert next_required_question(_session(), answers) is None


def test_follow_up_is_asked_even_when_the_model_not_the_fallback_asked_the_yes_no():
    answers = _answers(*_ALL_COVERED_WITH_NO[:4], ("¿Ha notado algún cambio reciente en su peso?", "Sí"))
    question, _ = next_required_question(_session(), answers)
    assert "kilos" in question


def test_follow_up_is_not_asked_again_once_answered():
    answers = _replace(_ALL_COVERED_WITH_NO, 0, "Sí") + _answers(
        ("¿Qué medicación o suplementos toma, y con qué frecuencia?", "Carbonato cálcico, a diario")
    )
    assert next_required_question(_session(), answers) is None


def test_model_wording_condicion_medica_covers_antecedents_and_asks_for_detail():
    # live run (D-026): the model asked "¿otra condición médica?" → "Sí", the
    # keywords missed it, and the fixed antecedents question was asked on top
    answers = _answers(
        ("¿Toma alguna medicación?", "No"),
        ("¿Ha tenido alguna otra condición médica además del reflujo?", "Sí"),
        ("¿Desde cuándo tiene el problema?", "Hace un año"),
        ("¿Tiene alguna alergia alimentaria?", "No"),
        ("¿Ha cambiado su peso?", "No"),
    )
    assert "antecedents" not in _keys(get_missing_topics(_session(), answers))
    question, _ = next_required_question(_session(), answers)
    assert question.startswith("¿Qué enfermedad le diagnosticaron")


def test_uncovered_topics_come_before_follow_ups():
    answers = _answers(("¿Toma alguna medicación?", "Sí"))
    question, _ = next_required_question(_session(), answers)
    assert question == "¿Le han diagnosticado alguna enfermedad o le han operado alguna vez?"


# --- the fixed fallback questions themselves -------------------------------------------------


_ALL_SESSIONS = [
    _session(mode, specialty)
    for mode in (ConsultationMode.FIRST_VISIT, ConsultationMode.FOLLOW_UP)
    for specialty in ("Nutrición", "Fisioterapia")
]


@pytest.mark.parametrize("session", _ALL_SESSIONS)
def test_each_fallback_question_covers_its_own_topic_so_it_is_never_asked_twice(session):
    for topic in get_mandatory_topics(session):
        answers = _answers((topic.fallback_question, "No"))
        assert topic.key not in _keys(get_missing_topics(session, answers)), topic.key


@pytest.mark.parametrize("session", _ALL_SESSIONS)
def test_fixed_questions_pass_the_regulatory_guardrail(session):
    # shown to the patient without going through generate_safely, so they
    # must pass the same filter by construction
    for topic in get_mandatory_topics(session):
        for question in (topic.fallback_question, topic.follow_up_question):
            if question is None:
                continue
            result = check_output(question)
            assert result.is_safe, f"{topic.key}: {question!r} — {result.violations}"
