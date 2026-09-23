import pytest

from raup.codes import generate_code


def test_default_length():
    assert len(generate_code()) == 6


def test_custom_length():
    assert len(generate_code(length=8)) == 8


def test_rejects_too_short_length():
    with pytest.raises(ValueError):
        generate_code(length=3)


def test_does_not_use_ambiguous_characters():
    ambiguous = set("0O1IL")
    codes = {generate_code(length=20) for _ in range(20)}
    used_characters = set("".join(codes))
    assert used_characters.isdisjoint(ambiguous)


def test_is_reasonably_random():
    codes = {generate_code() for _ in range(200)}
    # with a 32-symbol alphabet and length 6, collisions are extremely
    # unlikely across 200 samples
    assert len(codes) == 200
