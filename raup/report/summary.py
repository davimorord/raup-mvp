"""Executive summary generation — strictly declarative, see D-004.

Summarizes only what the patient reported. The safety preamble (applied by
generate_safely) already forbids diagnosis/interpretation; this prompt
reinforces it for this specific task.
"""

from __future__ import annotations

from raup.llm.base import LLMClient
from raup.llm.safe_client import generate_safely
from raup.models import Answer, Session
from raup.report.extraction import build_transcript

_SYSTEM_PROMPT = """
Write a short executive summary, in Spanish, for the clinician who is about to see this \
patient. Summarize ONLY what the patient reported in the transcript below — never add an \
interpretation, a possible cause, a diagnosis, or a recommendation. Write it as a clinician's \
handoff note: neutral, factual, in third person ("El paciente refiere..."), 3-5 sentences. Keep \
the concrete details the patient gave — the names of any medication, how often and for how long \
they take it (including a change in that frequency), timeframes, and named foods or symptoms — \
rather than generalizing them away ("uses antacids" loses what the clinician most needs). Never \
state more than the patient said: a bare "Sí" to "medication or supplements?" means one or the \
other, not both.
""".strip()


def generate_executive_summary(llm_client: LLMClient, session: Session, answers: list[Answer]) -> str:
    user_prompt = f"Specialty: {session.specialty}\n\nTranscript:\n{build_transcript(answers)}"
    return generate_safely(llm_client, _SYSTEM_PROMPT, user_prompt)
