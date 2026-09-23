"""Deterministic safety filter over LLM output (see DECISIONS.md D-004, D-016).

This is the MDR Class I regulatory backstop: no matter what the LLM
produces, this filter is the last line of defense before any LLM-generated
text reaches a patient or clinician. It never lets diagnostic, prescriptive,
or clinically-interpretive language through, checked deterministically by
pattern rather than by trusting a second model's judgment — a threshold-like
mechanism, consistent with how alert thresholds work elsewhere in the app
(D-009): auditable rules, not free-form AI judgment.

The real LLM output is always in Spanish (see raup/llm/prompts.py), so every
pattern here is Spanish. Intentionally conservative: false positives
(blocking safe text) are an acceptable cost, false negatives (letting unsafe
text through) are not.

KNOWN LIMITATION (to document in the thesis writeup): this is a first pass
built from plausible unsafe phrasings, not from real MedGemma output — there
was no live endpoint to test against yet when it was written (see D-008).
It must be re-tuned once Step 4 stands up the real endpoint and Steps 5/6
produce real model output to check it against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Assertive claims about the patient having/suffering a specific condition.
_DIAGNOSTIC_PATTERNS = [
    r"\btiene[s]?\s+(un|una|el|la)?\s*\w{0,15}\s*(depresi[oó]n|ansiedad|trastorno|s[ií]ndrome|enfermedad|hernia|fibromialgia|diabetes|anorexia|bulimia|fractura|tendinitis)",
    r"\bpadece[s]?\b",
    r"\bsufre[s]?\s+de\b",
    r"\bdiagn[oó]stico\s+de\b",
    r"\best[aá]s?\s+diagnosticad[oa]\b",
    r"\bes\s+(muy\s+)?probable\s+que\s+(tenga|tengas)\b",
    r"\bse\s+trata\s+de\s+(un|una)\s+caso\s+de\b",
    r"\besto\s+(indica|significa|sugiere)\s+que\s+(tiene|tienes)\b",
]

# Clinical interpretation / causal explanation, even without naming a
# condition outright — still forbidden (see SAFETY_PREAMBLE).
_INTERPRETIVE_PATTERNS = [
    r"\besto\s+(podr[ií]a|puede)\s+deberse\s+a\b",
    r"\bla\s+causa\s+(de\s+esto\s+)?(podr[ií]a\s+ser|es)\b",
    r"\besto\s+es\s+consecuencia\s+de\b",
    r"\besto\s+parece\s+ser\b",
]

# Treatment, medication, dosage, or any other prescriptive recommendation.
_TREATMENT_PATTERNS = [
    r"\bdeber[ií]as?\s+tomar\b",
    r"\bdeber[ií]as?\s+(hacer|realizar|empezar|evitar|dejar)\b",
    r"\bte\s+recomiendo\b",
    r"\ble\s+recomiendo\b",
    r"\bempiece\s+a\s+tomar\b",
    r"\bempieza\s+a\s+tomar\b",
    r"\btratamiento\s+(adecuado|recomendado|indicado)\s+es\b",
    r"\bdebe(s)?\s+(hacer|realizar|guardar|iniciar)\s+reposo\b",
    r"\b\d+\s?(mg|mcg|ml|g|comprimidos?|pastillas?|c[aá]psulas?)\b",
    r"\ble\s+prescribo\b",
    r"\bte\s+prescribo\b",
]

_ALL_PATTERNS: list[tuple[str, str]] = (
    [(p, "diagnostic") for p in _DIAGNOSTIC_PATTERNS]
    + [(p, "interpretive") for p in _INTERPRETIVE_PATTERNS]
    + [(p, "treatment") for p in _TREATMENT_PATTERNS]
)


@dataclass
class GuardrailResult:
    is_safe: bool
    violations: list[str] = field(default_factory=list)
    """Human-readable reasons, for logs/debugging only — never shown to the
    end user, since they'd quote the unsafe text back."""


def check_output(text: str) -> GuardrailResult:
    """Scans `text` for diagnostic, interpretive, or prescriptive language.

    Deterministic and pattern-based on purpose (see module docstring): this
    is the regulatory backstop, not a heuristic best-effort check."""

    lowered = text.lower()
    violations = [
        f"{category} language matched: {pattern!r}"
        for pattern, category in _ALL_PATTERNS
        if re.search(pattern, lowered)
    ]
    return GuardrailResult(is_safe=not violations, violations=violations)
