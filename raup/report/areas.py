"""Areas-to-explore generation: what the clinician should ask about further,
never what to do about it — see D-004.
"""

from __future__ import annotations

from raup.llm.base import LLMClient
from raup.llm.safe_client import generate_safely
from raup.models import Answer, Session
from raup.report.extraction import build_transcript

_MAX_AREAS = 5  # hard cap in code too, not just requested in the prompt — a
# live test showed the model can fall into a repetitive loop ("¿Ha notado
# algún cambio en su relación con la tecnología/la política/el arte...?")
# and run to the token limit otherwise (see D-022).

_SYSTEM_PROMPT = f"""
List, in Spanish, at most {_MAX_AREAS} topics the clinician should ask more about during the \
consultation — gaps, vague answers, or anything that would benefit from more detail. Phrase \
every item as a topic to explore or a question to ask, NEVER as an action to take, a \
recommendation, or a conclusion about what's wrong. One item per line, starting with "- ". Stop \
after the most important ones — do not pad the list with minor or repetitive items. If nothing \
meaningful is missing, respond with a single line: "- Ninguna área adicional a destacar."
""".strip()


def generate_areas_to_explore(llm_client: LLMClient, session: Session, answers: list[Answer]) -> list[str]:
    user_prompt = f"Specialty: {session.specialty}\n\nTranscript:\n{build_transcript(answers)}"
    raw_response = generate_safely(llm_client, _SYSTEM_PROMPT, user_prompt)
    areas = [line.strip().lstrip("-").strip() for line in raw_response.splitlines() if line.strip().startswith("-")]
    return [a for a in areas if a][:_MAX_AREAS]
