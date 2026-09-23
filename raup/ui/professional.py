"""Clinician screen: create sessions and look up their status/report.

No login (out of scope for the MVP, see CLAUDE.md): anyone who opens the app
without `?code=` in the URL sees this screen.
"""

from __future__ import annotations

import streamlit as st

from raup.codes import generate_code
from raup.config import build_patient_link
from raup.models import ConsultationMode, DEFAULT_SPECIALTY, Session, SessionStatus
from raup.repository.base import AnswerRepository, ReportRepository, SessionRepository

# NOTE: dict values below are shown directly in the UI and must stay in
# Spanish — this is a real pilot with Spanish-speaking dietitians.
MODE_LABELS = {
    ConsultationMode.FIRST_VISIT: "Primera consulta",
    ConsultationMode.FOLLOW_UP: "Seguimiento",
}

_STATUS_LABELS = {
    SessionStatus.CREATED: "Creada — el paciente aún no ha entrado",
    SessionStatus.IN_PROGRESS: "En curso — el paciente está respondiendo",
    SessionStatus.COMPLETED: "Completada",
}

_MAX_UNIQUE_CODE_ATTEMPTS = 3


def show_professional_page(
    session_repo: SessionRepository, answer_repo: AnswerRepository, report_repo: ReportRepository
) -> None:
    st.title("RaUP — panel del profesional")

    create_tab, lookup_tab = st.tabs(["Nueva sesión", "Consultar sesión"])

    with create_tab:
        _show_new_session_form(session_repo)

    with lookup_tab:
        _show_session_lookup(session_repo, answer_repo, report_repo)


def _show_new_session_form(session_repo: SessionRepository) -> None:
    with st.form("nueva_sesion"):
        mode_label = st.radio(
            "Tipo de consulta",
            options=list(MODE_LABELS.values()),
            horizontal=True,
        )
        specialty = st.text_input(
            "Especialidad",
            value=DEFAULT_SPECIALTY,
            help="Precargado para el piloto de nutrición. Puedes escribir cualquier otra especialidad.",
        )
        reason = st.text_area(
            "Motivo de consulta (opcional, pero muy recomendable)",
            placeholder="p.ej. dolor lumbar de 3 semanas de evolución",
            help="Cuanto más contexto des aquí, más relevantes serán las preguntas del cuestionario.",
        )
        submitted = st.form_submit_button("Generar sesión para el paciente")

    if submitted:
        _create_session(session_repo, mode_label, specialty, reason)

    created_session = st.session_state.get("raup_last_session")
    if created_session:
        st.success("Sesión creada.")
        st.metric("Código para el paciente", created_session.code)
        link = build_patient_link(created_session.code)
        if link:
            st.write(f"Enlace directo: {link}")
        else:
            st.caption("Comparte este código con el paciente para que acceda al cuestionario.")


def _create_session(session_repo: SessionRepository, mode_label: str, specialty: str, reason: str) -> None:
    mode = next(m for m, label in MODE_LABELS.items() if label == mode_label)
    session = Session(
        code=generate_code(),
        mode=mode,
        specialty=specialty.strip() or DEFAULT_SPECIALTY,
        consultation_reason=reason.strip() or None,
    )

    for _ in range(_MAX_UNIQUE_CODE_ATTEMPTS):
        try:
            session_repo.create(session)
            st.session_state["raup_last_session"] = session
            return
        except ValueError:
            # code collision (extremely unlikely) — retry with a new one
            session.code = generate_code()

    st.error("No se pudo generar un código único tras varios intentos. Inténtalo de nuevo.")


def _show_session_lookup(
    session_repo: SessionRepository, answer_repo: AnswerRepository, report_repo: ReportRepository
) -> None:
    code = st.text_input("Código de la sesión").strip().upper()
    if not code:
        return

    session = session_repo.get_by_code(code)
    if session is None:
        st.error("No existe ninguna sesión con ese código.")
        return

    st.write(f"**Modo:** {MODE_LABELS[session.mode]}")
    st.write(f"**Especialidad:** {session.specialty}")
    if session.consultation_reason:
        st.write(f"**Motivo de consulta:** {session.consultation_reason}")
    st.write(f"**Estado:** {_STATUS_LABELS[session.status]}")

    if session.status != SessionStatus.COMPLETED:
        st.info("El informe estará disponible cuando el paciente complete el cuestionario.")
        return

    report = report_repo.get_by_session(session.id)
    if report is None:
        st.warning(
            "La sesión está completada pero el informe todavía no se ha generado "
            "(puede haber fallado; abajo tienes las respuestas en bruto del paciente)."
        )
    else:
        st.subheader("Resumen ejecutivo")
        st.write(report.executive_summary)
        if report.alerts:
            st.subheader("Señales de alerta")
            for alert in report.alerts:
                st.warning(f"**{alert.source}** — {alert.message}")
        if report.areas_to_explore:
            st.subheader("Áreas a profundizar")
            for area in report.areas_to_explore:
                st.write(f"- {area}")

    _show_raw_transcript(answer_repo, session.id)


def _show_raw_transcript(answer_repo: AnswerRepository, session_id: str) -> None:
    answers = answer_repo.list_by_session(session_id)
    if not answers:
        return
    with st.expander("Ver respuestas del paciente (sin resumir)"):
        for answer in answers:
            st.write(f"**{answer.question}**")
            st.write(answer.answer)
