"""Deterministic duplicate-question detection (see D-024).

A live test showed MedGemma will re-ask a question it already asked —
sometimes near-verbatim — despite an explicit "never repeat" instruction in
the prompt. Text instructions aren't a guarantee (the same lesson as D-009,
D-016, D-020, D-022): this is the code-level backstop, checked before a
question is ever shown to the patient.
"""

from __future__ import annotations

import difflib
import re

from raup.models import Answer

_SIMILARITY_THRESHOLD = 0.75


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def is_duplicate_question(question: str, previous_answers: list[Answer]) -> bool:
    normalized_new = _normalize(question)
    if not normalized_new:
        return False
    return any(
        difflib.SequenceMatcher(None, normalized_new, _normalize(answer.question)).ratio() >= _SIMILARITY_THRESHOLD
        for answer in previous_answers
    )
