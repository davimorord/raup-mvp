"""Areas-to-explore generation: what the clinician should ask about further,
never what to do about it — see D-004.
"""

from __future__ import annotations

from raup.llm.base import LLMClient
from raup.llm.safe_client import generate_safely
from raup.models import Answer, Session
from raup.questionnaire.dedup import is_duplicate_question
from raup.report.extraction import build_transcript

_MAX_AREAS = 5  # hard cap in code too, not just requested in the prompt — a
# live test showed the model can fall into a repetitive loop ("¿Ha notado
# algún cambio en su relación con la tecnología/la política/el arte...?")
# and run to the token limit otherwise (see D-022).

_SYSTEM_PROMPT = f"""
List, in Spanish, at most {_MAX_AREAS} topics the clinician should ask more about during the \
consultation — gaps, vague answers, or anything that would benefit from more detail. Phrase \
every item as a topic to explore or a question to ask, NEVER as an action to take, a \
recommendation, or a conclusion about what's wrong. Every item must be about something \
DIFFERENT, and must not repeat a question already asked in the transcript. One item per line, \
starting with "- ". Stop after the most important ones — do not pad the list with minor or \
repetitive items. If nothing meaningful is missing, respond with a single line: \
"- Ninguna área adicional a destacar."
""".strip()


def _drop_repeats(areas: list[str], answers: list[Answer]) -> list[str]:
    """Deterministic filter (see D-026): a live run returned the same area 4
    times out of 5, each re-asking a question the patient had already
    answered. Drops an area that repeats an earlier area or an asked question."""
    kept: list[str] = []
    for area in areas:
        seen = answers + [Answer(session_id="", order=0, question=k, answer="") for k in kept]
        if not is_duplicate_question(area, seen):
            kept.append(area)
    return kept


def _is_truncated(area: str) -> bool:
    # a live run ended with "¿Podría describir" — output cut at the token
    # limit mid-question. An opened "¿" that never closes is unfinished.
    return area.startswith("¿") and "?" not in area


def generate_areas_to_explore(llm_client: LLMClient, session: Session, answers: list[Answer]) -> list[str]:
    user_prompt = f"Specialty: {session.specialty}\n\nTranscript:\n{build_transcript(answers)}"
    raw_response = generate_safely(llm_client, _SYSTEM_PROMPT, user_prompt)
    areas = [line.strip().lstrip("-").strip() for line in raw_response.splitlines() if line.strip().startswith("-")]
    complete = [a for a in areas if a and not _is_truncated(a)]
    return _drop_repeats(complete, answers)[:_MAX_AREAS]
