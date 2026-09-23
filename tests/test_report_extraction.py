from raup.report.extraction import ExtractedFields, extract_fields, parse_extraction
from tests.fakes import FakeLLMClient


def test_parses_all_fields_when_well_formed():
    raw = (
        "WEIGHT_LOSS_KG: 8\n"
        "WEIGHT_BEFORE_KG: 70\n"
        "WEIGHT_LOSS_PERIOD_MONTHS: 3\n"
        "SELF_INDUCED_VOMITING: YES\n"
        "LOSS_OF_CONTROL_EATING: NO\n"
        "BODY_IMAGE_DISTORTION: YES\n"
        "FOOD_PREOCCUPATION: UNKNOWN"
    )
    fields = parse_extraction(raw)
    assert fields == ExtractedFields(
        weight_loss_kg=8.0,
        weight_before_kg=70.0,
        weight_loss_period_months=3.0,
        self_induced_vomiting=True,
        loss_of_control_eating=False,
        body_image_distortion=True,
        food_preoccupation=None,
    )


def test_weight_loss_percent_is_computed_not_extracted():
    fields = parse_extraction("WEIGHT_LOSS_KG: 8\nWEIGHT_BEFORE_KG: 70")
    assert round(fields.weight_loss_percent, 2) == round(8 / 70 * 100, 2)


def test_weight_loss_percent_is_none_without_a_baseline():
    fields = parse_extraction("WEIGHT_LOSS_KG: 8")
    assert fields.weight_loss_percent is None


def test_unknown_and_unparseable_become_none_everywhere():
    raw = "WEIGHT_LOSS_KG: UNKNOWN\nSELF_INDUCED_VOMITING: quizás"
    fields = parse_extraction(raw)
    assert fields.weight_loss_kg is None
    assert fields.self_induced_vomiting is None


def test_missing_lines_default_to_none_rather_than_crash():
    fields = parse_extraction("this response does not follow the format at all")
    assert fields == ExtractedFields()
    assert fields.weight_loss_percent is None


def test_extract_fields_calls_llm_and_parses_response():
    client = FakeLLMClient(responses=["WEIGHT_LOSS_KG: 7\nWEIGHT_LOSS_PERIOD_MONTHS: 2"])
    fields = extract_fields(client, answers=[])
    assert fields.weight_loss_kg == 7.0
    assert fields.weight_loss_period_months == 2.0
