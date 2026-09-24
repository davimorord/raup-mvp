"""Deterministic alert thresholds (see D-009, D-022).

Every threshold here is a fixed, cited number — never the LLM's judgment.
raup/report/extraction.py supplies the facts; this module only compares
them against published cutoffs. Nutrition-only for now (see D-019): if
`specialty` doesn't match nutrition, no alerts are computed — psychology
and physiotherapy instruments from D-009 aren't implemented yet.
"""

from __future__ import annotations

from raup.models import Alert
from raup.report.extraction import ExtractedFields
from raup.specialty import is_nutrition


def applies_to(specialty: str) -> bool:
    return is_nutrition(specialty)


def _must_weight_loss_alert(fields: ExtractedFields) -> list[Alert]:
    """MUST (Malnutrition Universal Screening Tool), weight-loss component
    only — full MUST also scores BMI and an acute-disease effect, neither
    of which this questionnaire reliably collects (see D-022). Cutoffs:
    <5% low risk, 5-10% medium, >=10% high risk of malnutrition.
    Source: https://www.mdcalc.com/calc/10190/malnutrition-universal-screening-tool-must
    """

    if fields.weight_loss_percent is None:
        return []

    pct = fields.weight_loss_percent
    if pct >= 10:
        return [
            Alert(
                code="MUST_ALTO",
                message=f"Pérdida de peso referida de {pct:g}% — riesgo alto según MUST (componente de peso).",
                source="MUST (simplificado — solo % de pérdida de peso)",
            )
        ]
    if pct >= 5:
        return [
            Alert(
                code="MUST_MEDIO",
                message=f"Pérdida de peso referida de {pct:g}% — riesgo medio según MUST (componente de peso).",
                source="MUST (simplificado — solo % de pérdida de peso)",
            )
        ]
    return []


def _eating_behavior_alert(fields: ExtractedFields) -> list[Alert]:
    """Adapted from SCOFF: the validated instrument is 5 yes/no items with a
    cutoff of >=2 affirmative answers. This uses 4 of the 5 items — the
    weight-loss item is covered separately by the MUST check above, to
    avoid extracting weight loss twice — so this is an approximate
    derivative, not the literal validated SCOFF (see D-022).
    Source: https://pubmed.ncbi.nlm.nih.gov/19343793/
    """

    items = [
        fields.self_induced_vomiting,
        fields.loss_of_control_eating,
        fields.body_image_distortion,
        fields.food_preoccupation,
    ]
    affirmative = sum(1 for item in items if item is True)
    if affirmative >= 2:
        return [
            Alert(
                code="SCOFF_POSITIVO",
                message=f"{affirmative} de 4 señales de conducta alimentaria de riesgo referidas (adaptado de SCOFF).",
                source="SCOFF (adaptado — 4 de 5 ítems)",
            )
        ]
    return []


def compute_alerts(specialty: str, fields: ExtractedFields) -> list[Alert]:
    if not applies_to(specialty):
        return []
    return _must_weight_loss_alert(fields) + _eating_behavior_alert(fields)
