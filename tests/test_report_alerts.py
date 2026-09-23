from raup.report.alerts import applies_to, compute_alerts
from raup.report.extraction import ExtractedFields


def _with_weight_loss_percent(percent: float) -> ExtractedFields:
    # weight_loss_percent is computed (kg / before_kg * 100) — base 100kg
    # makes weight_loss_kg equal to the desired percent, for readable tests.
    return ExtractedFields(weight_loss_kg=percent, weight_before_kg=100)


def test_applies_to_nutrition_variants():
    assert applies_to("Nutrición")
    assert applies_to("nutricion")
    assert applies_to("Nutrición clínica")


def test_does_not_apply_to_other_specialties():
    assert not applies_to("Fisioterapia")
    assert not applies_to("Psicología")


def test_no_alerts_for_non_nutrition_specialty_even_with_concerning_fields():
    fields = _with_weight_loss_percent(15)
    assert compute_alerts("Fisioterapia", fields) == []


def test_no_weight_loss_alert_when_percent_unknown():
    fields = ExtractedFields()
    assert compute_alerts("Nutrición", fields) == []


def test_no_weight_loss_alert_when_only_kg_known_without_baseline():
    # can't compute a percentage without a starting weight — no guessing
    fields = ExtractedFields(weight_loss_kg=8)
    assert compute_alerts("Nutrición", fields) == []


def test_no_weight_loss_alert_below_five_percent():
    fields = _with_weight_loss_percent(3)
    assert compute_alerts("Nutrición", fields) == []


def test_medium_weight_loss_alert_between_five_and_ten_percent():
    alerts = compute_alerts("Nutrición", _with_weight_loss_percent(7))
    assert len(alerts) == 1
    assert alerts[0].code == "MUST_MEDIO"


def test_high_weight_loss_alert_at_or_above_ten_percent():
    alerts = compute_alerts("Nutrición", _with_weight_loss_percent(10))
    assert len(alerts) == 1
    assert alerts[0].code == "MUST_ALTO"


def test_percent_is_computed_from_kg_and_baseline_not_asked_of_the_llm():
    # 8kg lost from a 70kg baseline is ~11.4%, not "8%" — this is exactly
    # the bug a live MedGemma test surfaced (see D-022): the model can't be
    # trusted to do this division itself.
    fields = ExtractedFields(weight_loss_kg=8, weight_before_kg=70)
    assert round(fields.weight_loss_percent, 1) == 11.4
    alerts = compute_alerts("Nutrición", fields)
    assert alerts[0].code == "MUST_ALTO"


def test_no_eating_behavior_alert_with_fewer_than_two_affirmative_items():
    fields = ExtractedFields(self_induced_vomiting=True)
    assert compute_alerts("Nutrición", fields) == []


def test_eating_behavior_alert_with_two_or_more_affirmative_items():
    fields = ExtractedFields(self_induced_vomiting=True, loss_of_control_eating=True)
    alerts = compute_alerts("Nutrición", fields)
    assert len(alerts) == 1
    assert alerts[0].code == "SCOFF_POSITIVO"


def test_both_alerts_can_fire_together():
    fields = ExtractedFields(
        weight_loss_kg=12,
        weight_before_kg=100,
        self_induced_vomiting=True,
        body_image_distortion=True,
    )
    alerts = compute_alerts("Nutrición", fields)
    codes = {a.code for a in alerts}
    assert codes == {"MUST_ALTO", "SCOFF_POSITIVO"}


def test_alert_messages_never_diagnose_or_prescribe():
    from raup.llm.guardrails import check_output

    fields = ExtractedFields(
        weight_loss_kg=12, weight_before_kg=100, self_induced_vomiting=True, loss_of_control_eating=True
    )
    for alert in compute_alerts("Nutrición", fields):
        result = check_output(alert.message)
        assert result.is_safe, f"alert message flagged unsafe: {alert.message!r} — {result.violations}"
