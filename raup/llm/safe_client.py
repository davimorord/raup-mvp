"""Safety wrapper around an LLMClient (see D-004, D-016).

Steps 5 and 6 must call `generate_safely` instead of talking to an
LLMClient directly — it's the only path in this codebase guaranteed to
never hand diagnostic, interpretive, or prescriptive language to a user.
It prepends the shared safety preamble (raup/llm/prompts.py) to every
system prompt, checks every response against the deterministic guardrail
(raup/llm/guardrails.py), and retries with a stronger reminder before
giving up.
"""

from __future__ import annotations

import logging

from raup.llm.base import LLMClient
from raup.llm.guardrails import check_output
from raup.llm.prompts import SAFETY_PREAMBLE

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_RETRY_REMINDER = (
    "Your previous answer violated a safety rule and was discarded: it "
    "contained diagnostic, interpretive, or prescriptive language. Rewrite "
    "it from scratch, following every rule in the system prompt exactly — "
    "say nothing about what the patient has, why, or what they should do."
)


class UnsafeOutputError(RuntimeError):
    """Raised when the LLM keeps producing unsafe output after every retry.

    Callers must not fall back to showing the raw (unsafe) output — surface
    this as a generic error instead."""


def generate_safely(client: LLMClient, system_prompt: str, user_prompt: str) -> str:
    full_system_prompt = f"{SAFETY_PREAMBLE}\n\n{system_prompt}".strip()
    prompt = user_prompt

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        output = client.complete(full_system_prompt, prompt)
        result = check_output(output)
        if result.is_safe:
            return output

        logger.warning("Unsafe LLM output on attempt %d/%d: %s", attempt, _MAX_ATTEMPTS, result.violations)
        prompt = f"{user_prompt}\n\n{_RETRY_REMINDER}"

    raise UnsafeOutputError(
        f"The LLM produced unsafe output {_MAX_ATTEMPTS} times in a row; refusing to show it."
    )
