"""Tests for the regulatory safety filter (see CLAUDE.md, MDR Class I rule).

This is the single most important test file in the project: it's the
evidence that the system cannot leak diagnostic, interpretive, or
prescriptive language, across the three specialties in scope.
"""

import pytest

from raup.llm.guardrails import check_output

UNSAFE_DIAGNOSTIC_EXAMPLES = [
    "Tienes ansiedad generalizada.",
    "Parece que padeces depresión desde hace varios meses.",
    "Sufres de un trastorno de la conducta alimentaria.",
    "El diagnóstico de fibromialgia encaja con tus síntomas.",
    "Estás diagnosticado de hernia discal, según lo que describes.",
    "Es muy probable que tengas diabetes tipo 2.",
    "Se trata de un caso de bulimia nerviosa.",
    "Esto indica que tienes un síndrome de intestino irritable.",
]

UNSAFE_INTERPRETIVE_EXAMPLES = [
    "Esto podría deberse a un exceso de estrés laboral.",
    "La causa de esto es probablemente una mala postura mantenida.",
    "Esto es consecuencia de no dormir lo suficiente.",
    "Esto parece ser un cuadro de ansiedad anticipatoria.",
]

UNSAFE_TREATMENT_EXAMPLES = [
    "Deberías tomar un analgésico cada 8 horas.",
    "Te recomiendo hacer reposo absoluto durante una semana.",
    "Le recomiendo reducir el consumo de gluten de forma progresiva.",
    "Empieza a tomar 500 mg de paracetamol si el dolor persiste.",
    "El tratamiento adecuado es la terapia cognitivo-conductual semanal.",
    "Debes guardar reposo hasta que remita el dolor.",
    "Te prescribo 20 mg de omeprazol en ayunas.",
]

SAFE_EXAMPLES = [
    "¿Desde cuándo nota este dolor lumbar?",
    "¿Cómo describiría su calidad de sueño en las últimas dos semanas?",
    "El paciente refiere dolor lumbar de 3 semanas de evolución, sin tratamiento previo.",
    "Indica que ha perdido peso de forma involuntaria en el último mes.",
    "¿Ha notado cambios en su apetito recientemente?",
    "Resumen: la paciente describe episodios de ansiedad antes de eventos sociales, "
    "sin haber consultado antes por este motivo.",
    "Área a profundizar: patrón de sueño y su relación con el dolor referido.",
]


@pytest.mark.parametrize("text", UNSAFE_DIAGNOSTIC_EXAMPLES)
def test_flags_diagnostic_language(text):
    result = check_output(text)
    assert not result.is_safe, f"should have flagged: {text!r}"
    assert result.violations


@pytest.mark.parametrize("text", UNSAFE_INTERPRETIVE_EXAMPLES)
def test_flags_interpretive_language(text):
    result = check_output(text)
    assert not result.is_safe, f"should have flagged: {text!r}"


@pytest.mark.parametrize("text", UNSAFE_TREATMENT_EXAMPLES)
def test_flags_treatment_language(text):
    result = check_output(text)
    assert not result.is_safe, f"should have flagged: {text!r}"


@pytest.mark.parametrize("text", SAFE_EXAMPLES)
def test_allows_safe_text(text):
    result = check_output(text)
    assert result.is_safe, f"should NOT have flagged: {text!r} — violations: {result.violations}"
    assert result.violations == []


def test_is_case_insensitive():
    result = check_output("TIENES ANSIEDAD GENERALIZADA.")
    assert not result.is_safe


def test_reports_multiple_violations():
    result = check_output(
        "Tienes fibromialgia. Deberías tomar 400 mg de ibuprofeno al día."
    )
    assert not result.is_safe
    assert len(result.violations) >= 2
