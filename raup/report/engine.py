"""Report generation: ties extraction, alerts, summary, and areas-to-explore
together into a single Report — see D-022.
"""

from __future__ import annotations

from raup.llm.base import LLMClient
from raup.models import Answer, Report, Session
from raup.report.alerts import compute_alerts
from raup.report.areas import generate_areas_to_explore
from raup.report.extraction import extract_fields
from raup.report.summary import generate_executive_summary


def generate_report(llm_client: LLMClient, session: Session, answers: list[Answer]) -> Report:
    fields = extract_fields(llm_client, answers)
    alerts = compute_alerts(session.specialty, fields)
    executive_summary = generate_executive_summary(llm_client, session, answers)
    areas_to_explore = generate_areas_to_explore(llm_client, session, answers)

    return Report(
        session_id=session.id,
        executive_summary=executive_summary,
        alerts=alerts,
        areas_to_explore=areas_to_explore,
    )
