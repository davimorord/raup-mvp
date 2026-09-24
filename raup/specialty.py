"""Specialty matching for the free-text `Session.specialty` field (see D-019).

One place to decide "is this a nutrition consultation?", shared by the alert
engine (raup/report/alerts.py) and the questionnaire's mandatory-topic check
(raup/questionnaire/coverage.py), so the two can never disagree.
"""

from __future__ import annotations

_NUTRITION_KEYWORD = "nutrici"  # matches "Nutrición" / "nutricion" / "Nutrición clínica"


def is_nutrition(specialty: str) -> bool:
    return _NUTRITION_KEYWORD in specialty.lower()
