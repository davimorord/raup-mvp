import pytest

from raup.llm.prompts import SAFETY_PREAMBLE
from raup.llm.safe_client import UnsafeOutputError, generate_safely
from tests.fakes import FakeLLMClient


def test_returns_output_when_safe_on_first_try():
    client = FakeLLMClient(responses=["¿Desde cuándo nota este dolor?"])

    result = generate_safely(client, system_prompt="Ask about pain.", user_prompt="Start.")

    assert result == "¿Desde cuándo nota este dolor?"
    assert len(client.calls) == 1


def test_prepends_safety_preamble_to_system_prompt():
    client = FakeLLMClient(responses=["¿Cómo describiría su dolor?"])

    generate_safely(client, system_prompt="Ask about pain.", user_prompt="Start.")

    sent_system_prompt, _ = client.calls[0]
    assert SAFETY_PREAMBLE in sent_system_prompt
    assert "Ask about pain." in sent_system_prompt


def test_retries_and_recovers_when_first_attempt_unsafe():
    client = FakeLLMClient(
        responses=[
            "Tienes ansiedad generalizada.",  # unsafe, triggers a retry
            "¿Cómo describiría su estado de ánimo esta semana?",  # safe
        ]
    )

    result = generate_safely(client, system_prompt="Ask about mood.", user_prompt="Start.")

    assert result == "¿Cómo describiría su estado de ánimo esta semana?"
    assert len(client.calls) == 2


def test_raises_after_max_unsafe_attempts():
    client = FakeLLMClient(
        responses=[
            "Tienes ansiedad generalizada.",
            "Padeces un trastorno de ansiedad.",
            "Esto podría deberse a un exceso de estrés.",
        ]
    )

    with pytest.raises(UnsafeOutputError):
        generate_safely(client, system_prompt="Ask about mood.", user_prompt="Start.")

    assert len(client.calls) == 3


def test_never_returns_unsafe_text():
    """Even if it somehow got past the retries with unsafe text, the wrapper
    must raise rather than return it — this asserts the actual behavior of
    the exhausted-retries path, the safety-critical one."""
    client = FakeLLMClient(responses=["Deberías tomar 500 mg de paracetamol."] * 3)

    try:
        result = generate_safely(client, system_prompt="Ask.", user_prompt="Start.")
    except UnsafeOutputError:
        return  # expected: no unsafe text was ever returned
    pytest.fail(f"generate_safely returned unsafe text instead of raising: {result!r}")
