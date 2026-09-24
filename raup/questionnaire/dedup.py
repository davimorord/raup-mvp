"""Deterministic duplicate-question detection (see D-024, D-025).

A live test showed MedGemma will re-ask a question it already asked —
sometimes near-verbatim — despite an explicit "never repeat" instruction in
the prompt. Text instructions aren't a guarantee (the same lesson as D-009,
D-016, D-020, D-022): this is the code-level backstop, checked before a
question is ever shown to the patient.

Two independent checks, either one flags a duplicate:
1. Whole-string similarity (`difflib`), only when the topic words also match —
   catches exact and near-exact repeats without flagging same-template,
   different-topic questions ("...su apetito...?" vs "...su peso...?").
2. Content-word overlap — catches a shorter follow-up that re-asks part of a
   longer, multi-part earlier question, which string similarity misses
   because the lengths differ (a real case scored 0.72 against a 0.75
   threshold; see D-025). Filler words ("podría", "notado", "cambio"...) are
   ignored so only the topical words count.

Deliberately lexical: it cannot catch a pure synonym paraphrase. That limit
is accepted and documented rather than papered over with another LLM call.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

from raup.models import Answer

_SIMILARITY_THRESHOLD = 0.75
_OVERLAP_THRESHOLD = 0.8  # share of the shorter question's content words found in the other
_MIN_SHARED_CONTENT_WORDS = 3  # below this, sharing a topic word isn't a repeat
_STEM_LENGTH = 5  # crude stemming: alimentos/alimentación -> "alime"

# Question-framing filler, not topic: ignoring it is what lets "¿Podría indicar
# si ha notado algún cambio en X?" match "¿Podría describir ... diferencia ... X?"
# Interrogatives (cuándo, cómo, dónde, cuánto...) are deliberately NOT filler:
# they set the *angle* of a question ("since when" vs "how intense"), so two
# questions about the same topic with different interrogatives are different.
_FILLER_WORDS = frozenset(
    """
    a al algo algun alguna algunas alguno algunos ante con contra de del
    desde el ella ellos en entre era es esa ese eso esta este esto estos ha han has hay
    la las le les lo los me mi mis muy mas ni no nos o para pero por porque que se ser si sin
    sobre su sus tambien tan te tiene tienen tu tus un una uno unos y ya yo
    podria podrias puede pueden poder indicar indicarme describir decirme contarme explicar
    notado notar cambio cambios diferencia diferencias ultima ultimo ultimos ultimas consulta
    actualmente usted
    """.split()
)
_STEM_SIMILARITY_THRESHOLD = 0.5  # Jaccard of topic words for the string-similarity path


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _content_stems(text: str) -> set[str]:
    words = _strip_accents(_normalize(text)).split()
    return {word[:_STEM_LENGTH] for word in words if word not in _FILLER_WORDS and len(word) > 2}


def _same_topic(new: str, previous: str) -> bool:
    new_stems, previous_stems = _content_stems(new), _content_stems(previous)
    if not new_stems and not previous_stems:
        return True  # pure framing on both sides — nothing to tell them apart by
    union = new_stems | previous_stems
    return len(new_stems & previous_stems) / len(union) >= _STEM_SIMILARITY_THRESHOLD


def _is_similar_string(new: str, previous: str) -> bool:
    # String similarity alone would flag "...diferencia en su apetito...?" vs
    # "...diferencia en su peso...?" (same template, different topic) — a
    # legitimate pair, common in follow-up interviews. So it only counts when
    # the topic words also match.
    ratio = difflib.SequenceMatcher(None, _normalize(new), _normalize(previous)).ratio()
    return ratio >= _SIMILARITY_THRESHOLD and _same_topic(new, previous)


def _overlaps_in_content(new: str, previous: str) -> bool:
    new_stems, previous_stems = _content_stems(new), _content_stems(previous)
    shared = new_stems & previous_stems
    if len(shared) < _MIN_SHARED_CONTENT_WORDS:
        return False
    smaller = min(len(new_stems), len(previous_stems))
    return len(shared) / smaller >= _OVERLAP_THRESHOLD


def is_duplicate_question(question: str, previous_answers: list[Answer]) -> bool:
    if not _normalize(question):
        return False
    return any(
        _is_similar_string(question, answer.question) or _overlaps_in_content(question, answer.question)
        for answer in previous_answers
    )
