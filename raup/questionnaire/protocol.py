"""Parses the LLM's structured per-turn response.

The model is asked (see prompts.py) to answer in a fixed three-line format:

    QUESTION: <the question, in Spanish>
    TYPE: YES_NO | TEXT
    DONE: YES | NO

Parsing is deliberately lenient: a 4B model under a strict safety preamble
won't always follow the format exactly. Anything unparseable falls back to
the safest assumption (not done, free-text question, the raw response as
the question) rather than breaking the flow — see raup/llm/safe_client.py
for the same philosophy applied to safety instead of format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

QuestionType = Literal["YES_NO", "TEXT"]


@dataclass(frozen=True)
class ParsedStep:
    question: str
    question_type: QuestionType
    done: bool


_QUESTION_RE = re.compile(r"^\s*QUESTION\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_TYPE_RE = re.compile(r"^\s*TYPE\s*:\s*(YES_NO|TEXT)\s*$", re.IGNORECASE | re.MULTILINE)
_DONE_RE = re.compile(r"^\s*DONE\s*:\s*(YES|NO)\s*$", re.IGNORECASE | re.MULTILINE)

_WRAPPING_QUOTES = '"\'“”‘’'


def _strip_wrapping_quotes(text: str) -> str:
    # the model sometimes wraps the question in quote marks even though the
    # format doesn't ask for them (e.g. QUESTION: "¿...?") — strip one
    # matching pair, never quotes that are just part of the sentence.
    if len(text) >= 2 and text[0] in _WRAPPING_QUOTES and text[-1] in _WRAPPING_QUOTES:
        return text[1:-1].strip()
    return text


def parse_response(raw_text: str) -> ParsedStep:
    done_match = _DONE_RE.search(raw_text)
    done = bool(done_match) and done_match.group(1).upper() == "YES"

    type_match = _TYPE_RE.search(raw_text)
    question_type: QuestionType = "YES_NO" if type_match and type_match.group(1).upper() == "YES_NO" else "TEXT"

    question_match = _QUESTION_RE.search(raw_text)
    if question_match:
        question = question_match.group(1).strip()
    else:
        # no recognizable QUESTION: line — fall back to the whole response,
        # stripped of any other protocol lines that did parse
        question = _TYPE_RE.sub("", _DONE_RE.sub("", raw_text)).strip()

    return ParsedStep(question=_strip_wrapping_quotes(question), question_type=question_type, done=done)
