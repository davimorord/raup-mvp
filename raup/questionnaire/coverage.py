"""Mandatory-topic coverage check (see D-026).

A live test showed the model declaring the interview done after 46 s of a
420 s budget without ever asking about medication or antecedents. Whether a
topic was covered is checked here deterministically, by keyword, against
everything already asked and answered — the same "don't trust the model to
judge its own stopping point" pattern as budget.py and dedup.py.

Layered, not one fixed list: a core set depends on the consultation mode
(a follow-up doesn't re-ask antecedents or onset, already recorded at the
first visit), and specialty-specific topics are added on top only when they
apply (food allergies make no sense for a physiotherapy visit).

If a topic is still missing when the interview would otherwise end, the
engine asks a fixed, pre-written question about it — no extra LLM call, and
the wording is static, so it can't drift into diagnostic language.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from raup.models import Answer, ConsultationMode, Session
from raup.questionnaire.dedup import is_duplicate_question
from raup.specialty import is_nutrition


@dataclass(frozen=True)
class MandatoryTopic:
    key: str
    prompt_description: str  # English, fed to the LLM so it covers the topic naturally
    keywords: tuple[str, ...]  # accent-stripped, lowercase substrings that mark it as covered
    fallback_question: str  # Spanish, user-facing — shown as-is, never auto-translated
    fallback_type: str  # "YES_NO" or "TEXT"
    # Asked when the topic only ever got a bare "Sí": "takes medication: yes"
    # tells the clinician nothing useful — which one does (D-026).
    follow_up_question: str | None = None


# Keywords are matched against questions AND answers, so a patient who
# volunteers "tomo antiácidos a diario" has already covered medication.
# "medic" alone is deliberately avoided: it would match "médico" ("fui al
# médico") and mark medication as covered when it never came up.
_MEDICATION = MandatoryTopic(
    key="medication",
    prompt_description="Current medication or supplements (whether they take any, and which)",
    keywords=("medicac", "medicament", "farmac", "pastill", "suplement", "tratamiento"),
    fallback_question="¿Toma actualmente alguna medicación o suplemento?",
    fallback_type="YES_NO",
    follow_up_question="¿Qué medicación o suplementos toma, y con qué frecuencia?",
)
_MEDICATION_CHANGES = MandatoryTopic(
    key="medication_changes",
    prompt_description="Any change in medication or supplements since the last consultation",
    keywords=_MEDICATION.keywords,
    fallback_question="¿Ha habido algún cambio en su medicación o suplementos desde la última consulta?",
    fallback_type="YES_NO",
    follow_up_question="¿Qué ha cambiado en su medicación o suplementos, y desde cuándo?",
)
_ANTECEDENTS = MandatoryTopic(
    key="antecedents",
    prompt_description="Relevant medical history (previous illnesses, surgeries, known conditions)",
    keywords=(
        "antecedent", "enfermedad", "problema de salud", "patolog", "cirug",
        "operacion", "operad", "intervencion", "diagnostic",
        # the model's own wording in a live run: "¿Ha tenido alguna otra condición médica…?"
        "condicion medica", "condiciones medicas",
    ),
    # not "¿Tiene alguna enfermedad...?": the guardrail's "tiene + <condition>"
    # pattern can't tell a question from an assertion and blocks it (D-026)
    fallback_question="¿Le han diagnosticado alguna enfermedad o le han operado alguna vez?",
    fallback_type="YES_NO",
    follow_up_question="¿Qué enfermedad le diagnosticaron o de qué le operaron, y en qué año aproximadamente?",
)
_ONSET = MandatoryTopic(
    key="onset",
    prompt_description="When the problem started",
    keywords=(
        "desde cuando", "cuando comenz", "cuando empez", "comenzo", "empezo",
        "inicio", "origen", "aparecio", "hace cuanto",
    ),
    fallback_question="¿Desde cuándo tiene este problema?",
    fallback_type="TEXT",
)
_FOOD_ALLERGIES = MandatoryTopic(
    key="food_allergies",
    prompt_description="Food allergies or intolerances",
    keywords=("alerg", "intoleran"),
    fallback_question="¿Tiene alguna alergia o intolerancia alimentaria?",
    fallback_type="YES_NO",
    follow_up_question="¿A qué alimentos es alérgico o intolerante?",
)
# The weight follow-up asks for exactly what the MUST alert needs — kilograms
# changed, over how long, and the weight before — see raup/report/extraction.py.
_WEIGHT_CHANGES = MandatoryTopic(
    key="weight_changes",
    prompt_description="Recent weight changes",
    keywords=("peso", "bascula", "kilo"),
    fallback_question="¿Ha tenido cambios de peso en los últimos meses?",
    fallback_type="YES_NO",
    follow_up_question="¿Cuántos kilos ha cambiado, en cuánto tiempo, y cuánto pesaba antes?",
)
_WEIGHT_CHANGES_FOLLOW_UP = MandatoryTopic(
    key="weight_changes",
    prompt_description="Weight changes since the last consultation",
    keywords=_WEIGHT_CHANGES.keywords,
    fallback_question="¿Ha notado cambios en su peso desde la última consulta?",
    fallback_type="YES_NO",
    follow_up_question="¿Cuántos kilos ha cambiado desde la última consulta, y cuánto pesa ahora?",
)

_CORE = {
    ConsultationMode.FIRST_VISIT: (_MEDICATION, _ANTECEDENTS, _ONSET),
    ConsultationMode.FOLLOW_UP: (_MEDICATION_CHANGES,),
}
_NUTRITION_EXTRAS = {
    ConsultationMode.FIRST_VISIT: (_FOOD_ALLERGIES, _WEIGHT_CHANGES),
    ConsultationMode.FOLLOW_UP: (_WEIGHT_CHANGES_FOLLOW_UP,),
}


def _normalize(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return stripped.lower()


def get_mandatory_topics(session: Session) -> list[MandatoryTopic]:
    topics = list(_CORE[session.mode])
    if is_nutrition(session.specialty):
        topics.extend(_NUTRITION_EXTRAS[session.mode])
    return topics


def _mentions(topic: MandatoryTopic, answer: Answer) -> bool:
    text = _normalize(f"{answer.question} {answer.answer}")
    return any(keyword in text for keyword in topic.keywords)


def _is_covered(topic: MandatoryTopic, previous_answers: list[Answer]) -> bool:
    if any(_mentions(topic, a) for a in previous_answers):
        return True
    # keywords missed it, but an equivalent question was already asked —
    # never ask the fallback if the patient would feel asked twice
    return is_duplicate_question(topic.fallback_question, previous_answers)


def _bare(answer_text: str) -> str:
    return re.sub(r"[^\w]", "", _normalize(answer_text))


def _needs_detail(topic: MandatoryTopic, previous_answers: list[Answer]) -> bool:
    """True when the topic came up but only ever got a bare "Sí" — whether the
    yes/no question came from the model or from our own fallback."""
    if topic.follow_up_question is None:
        return False
    relevant = [a for a in previous_answers if _mentions(topic, a)]
    if not relevant or any(_bare(a.answer) not in ("si", "no") for a in relevant):
        return False  # never discussed, or there's already a real answer with detail
    if not any(_bare(a.answer) == "si" for a in relevant):
        return False  # only ever "No" — nothing to detail
    return not is_duplicate_question(topic.follow_up_question, previous_answers)


def get_missing_topics(session: Session, previous_answers: list[Answer]) -> list[MandatoryTopic]:
    return [topic for topic in get_mandatory_topics(session) if not _is_covered(topic, previous_answers)]


def next_required_question(session: Session, previous_answers: list[Answer]) -> tuple[str, str] | None:
    """The next fixed (question, type) the interview must still ask before it
    may end: an uncovered topic first, then a bare "Sí" that needs detail."""
    for topic in get_mandatory_topics(session):
        if not _is_covered(topic, previous_answers):
            return topic.fallback_question, topic.fallback_type
    for topic in get_mandatory_topics(session):
        if _needs_detail(topic, previous_answers):
            return topic.follow_up_question, "TEXT"
    return None
