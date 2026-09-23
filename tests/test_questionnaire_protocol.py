from raup.questionnaire.protocol import parse_response


def test_parses_well_formed_text_response():
    raw = "QUESTION: ¿Desde cuándo nota el dolor?\nTYPE: TEXT\nDONE: NO"
    result = parse_response(raw)
    assert result.question == "¿Desde cuándo nota el dolor?"
    assert result.question_type == "TEXT"
    assert result.done is False


def test_parses_well_formed_yes_no_response():
    raw = "QUESTION: ¿Ha tomado alguna medicación para esto?\nTYPE: YES_NO\nDONE: NO"
    result = parse_response(raw)
    assert result.question_type == "YES_NO"
    assert result.done is False


def test_parses_done_response():
    raw = "QUESTION:\nTYPE: TEXT\nDONE: YES"
    result = parse_response(raw)
    assert result.done is True


def test_is_case_insensitive_and_tolerates_whitespace():
    raw = "  question:   ¿Y el apetito?  \n type:text\ndone:no"
    result = parse_response(raw)
    assert result.question == "¿Y el apetito?"
    assert result.question_type == "TEXT"
    assert result.done is False


def test_falls_back_to_raw_text_when_format_is_missing():
    raw = "¿Cómo ha dormido esta semana?"
    result = parse_response(raw)
    assert result.question == "¿Cómo ha dormido esta semana?"
    assert result.question_type == "TEXT"
    assert result.done is False


def test_defaults_to_text_type_when_type_line_missing_or_invalid():
    raw = "QUESTION: ¿Algo más que contarnos?\nDONE: NO"
    result = parse_response(raw)
    assert result.question_type == "TEXT"
