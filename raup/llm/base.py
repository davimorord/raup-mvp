"""LLM client interface.

The rest of the app depends only on this interface, never on a specific
provider — see CLAUDE.md, process section. MedGemma is trained for medical
comprehension, not specifically for following strict conversational
instructions, so it may need to be swapped for a general-purpose model if
the guardrails (raup/llm/guardrails.py) aren't enough in practice. That swap
should only require a new implementation of this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Single-turn completion: given a system prompt and a user prompt,
        returns the model's raw text response. Callers are responsible for
        serializing any conversation history into `user_prompt` themselves —
        this interface deliberately stays provider-agnostic and stateless."""
