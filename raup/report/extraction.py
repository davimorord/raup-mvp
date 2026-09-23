"""Structured field extraction from the questionnaire transcript.

This is a comprehension task, not a clinical judgment: the LLM is asked to
read what the patient already said and pull out specific facts in a fixed
format. The deterministic threshold comparison against these facts happens
separately, in raup/report/alerts.py — see D-022. Extraction, never
diagnosis: the prompt explicitly forbids inferring anything not stated.

The model is only ever asked for raw numbers it can read directly off the
transcript (kilograms, a count of months) — never to compute anything
(a percentage, in particular). A live test showed MedGemma-4B will
literally copy a kilogram figure into a "percent" field instead of doing
the division; small models aren't reliable at arithmetic (see D-022).
Percentage calculation happens in Python, in `ExtractedFields.weight_loss_percent`.

Nutrition-specific on purpose for now (see D-019, D-022): the pilot is
nutrition-focused, and these fields back the MUST/SCOFF-inspired alerts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from raup.llm.base import LLMClient
from raup.llm.safe_client import generate_safely
from raup.models import Answer

_SYSTEM_PROMPT = """
You are reading a transcript of a pre-visit nutrition questionnaire and extracting specific \
facts the patient stated, exactly as they stated them. Do not infer, guess, calculate, or add \
anything the patient did not explicitly say — copy numbers directly, never compute one (e.g. \
never turn a kilogram figure into a percentage). If something wasn't addressed in the \
transcript, mark it UNKNOWN — never assume a value.

Respond in exactly this format, one line per field, nothing else:
WEIGHT_LOSS_KG: <number of kilograms the patient says they lost, or UNKNOWN>
WEIGHT_BEFORE_KG: <the patient's weight before that loss, in kilograms, or UNKNOWN>
WEIGHT_LOSS_PERIOD_MONTHS: <number, or UNKNOWN>
SELF_INDUCED_VOMITING: YES, NO, or UNKNOWN
LOSS_OF_CONTROL_EATING: YES, NO, or UNKNOWN
BODY_IMAGE_DISTORTION: YES, NO, or UNKNOWN
FOOD_PREOCCUPATION: YES, NO, or UNKNOWN
""".strip()


@dataclass(frozen=True)
class ExtractedFields:
    weight_loss_kg: Optional[float] = None
    weight_before_kg: Optional[float] = None
    weight_loss_period_months: Optional[float] = None
    self_induced_vomiting: Optional[bool] = None
    loss_of_control_eating: Optional[bool] = None
    body_image_distortion: Optional[bool] = None
    food_preoccupation: Optional[bool] = None

    @property
    def weight_loss_percent(self) -> Optional[float]:
        """Computed here, deterministically — never asked of the LLM (see
        module docstring)."""

        if self.weight_loss_kg is None or not self.weight_before_kg:
            return None
        return (self.weight_loss_kg / self.weight_before_kg) * 100


def _parse_number(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    match = re.search(r"-?\d+(\.\d+)?", raw)
    return float(match.group()) if match else None


def _parse_yes_no(raw: Optional[str]) -> Optional[bool]:
    value = (raw or "").strip().upper()
    if value == "YES":
        return True
    if value == "NO":
        return False
    return None  # covers UNKNOWN and anything unparseable — never guess


def _field(raw_text: str, name: str) -> Optional[str]:
    match = re.search(rf"^\s*{name}\s*:\s*(.+?)\s*$", raw_text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_extraction(raw_text: str) -> ExtractedFields:
    return ExtractedFields(
        weight_loss_kg=_parse_number(_field(raw_text, "WEIGHT_LOSS_KG")),
        weight_before_kg=_parse_number(_field(raw_text, "WEIGHT_BEFORE_KG")),
        weight_loss_period_months=_parse_number(_field(raw_text, "WEIGHT_LOSS_PERIOD_MONTHS")),
        self_induced_vomiting=_parse_yes_no(_field(raw_text, "SELF_INDUCED_VOMITING")),
        loss_of_control_eating=_parse_yes_no(_field(raw_text, "LOSS_OF_CONTROL_EATING")),
        body_image_distortion=_parse_yes_no(_field(raw_text, "BODY_IMAGE_DISTORTION")),
        food_preoccupation=_parse_yes_no(_field(raw_text, "FOOD_PREOCCUPATION")),
    )


def build_transcript(answers: list[Answer]) -> str:
    if not answers:
        return "(No answers recorded.)"
    return "\n".join(f'Q{a.order}: "{a.question}"\nA{a.order}: "{a.answer}"' for a in answers)


def extract_fields(llm_client: LLMClient, answers: list[Answer]) -> ExtractedFields:
    raw_response = generate_safely(llm_client, _SYSTEM_PROMPT, build_transcript(answers))
    return parse_extraction(raw_response)
