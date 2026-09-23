"""Information objectives the adaptive questionnaire tries to cover.

Specialty-agnostic on purpose: `Session.specialty` is free text (a nutrition
pilot by default, but not locked to it), so these are phrased as a generic
anamnesis checklist that the LLM adapts to the actual specialty and
consultation reason via the prompt (see raup/questionnaire/prompts.py), not
baked in here per specialty.
"""

from __future__ import annotations

from raup.models import ConsultationMode

_FIRST_VISIT_OBJECTIVES = [
    "Current situation: what the patient is experiencing right now, in their own words",
    "History: what has happened leading up to this consultation",
    "Incidents: any specific triggering event (a fall, an injury, a diagnosis, etc.)",
    "Antecedents: relevant medical history the patient is aware of",
    "Medication: what the patient is currently taking, if anything",
    "Origin: when and how the problem started",
    "Symptoms and their severity: what exactly, how intense (e.g. a 1-10 scale), how often",
]

_FOLLOW_UP_OBJECTIVES = [
    "Changes since the last consultation: better, worse, or the same, and how",
    "Adherence: whether the patient has followed what was agreed, and any incidents",
    "Current symptom status and severity",
    "Anything new the patient wants to flag before this consultation",
]

_OBJECTIVES = {
    ConsultationMode.FIRST_VISIT: _FIRST_VISIT_OBJECTIVES,
    ConsultationMode.FOLLOW_UP: _FOLLOW_UP_OBJECTIVES,
}


def get_objectives(mode: ConsultationMode) -> list[str]:
    return list(_OBJECTIVES[mode])
