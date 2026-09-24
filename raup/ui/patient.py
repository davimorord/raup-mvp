"""Patient screen: access by code, adaptive questionnaire, mobile-first.

One question per screen. The next question comes from
raup.questionnaire.engine, which enforces the time/question budget
deterministically (see D-018/D-019) — this module only renders whatever the
engine decides and persists each answer.
"""

from __future__ import annotations

import time

import streamlit as st

from raup.llm.base import LLMClient
from raup.models import Answer, DocumentMetadata, Session, SessionStatus
from raup.questionnaire.engine import QuestionnaireStep, get_next_step
from raup.report.engine import generate_report
from raup.repository.base import AnswerRepository, DocumentRepository, ReportRepository, SessionRepository
from raup.ui.professional import MODE_LABELS


def show_patient_page(
    session_repo: SessionRepository,
    answer_repo: AnswerRepository,
    document_repo: DocumentRepository,
    report_repo: ReportRepository,
    llm_client: LLMClient,
    code: str,
) -> None:
    st.title("RaUP")

    session = session_repo.get_by_code(code.strip().upper())
    if session is None:
        st.error("Este código no es válido o ha caducado. Consulta a tu profesional.")
        return

    if session.status == SessionStatus.COMPLETED:
        st.info("Este cuestionario ya está completado. Gracias.")
        return

    if session.status == SessionStatus.CREATED:
        session_repo.update_status(session.id, SessionStatus.IN_PROGRESS)

    elapsed_seconds = _get_elapsed_seconds(session)
    st.caption(f"Cuestionario de preconsulta — {MODE_LABELS[session.mode]}")

    step = _get_or_compute_step(session, answer_repo, llm_client, elapsed_seconds)

    if step.done:
        _finish_questionnaire(session, session_repo, answer_repo, report_repo, llm_client)
        st.success("¡Gracias! Hemos terminado. Tu profesional revisará esta información antes de la consulta.")
        _show_document_upload(document_repo, session.id)
        return

    _show_question(session, step, answer_repo)
    _show_document_upload(document_repo, session.id)


def _started_at_key(session: Session) -> str:
    return f"raup_started_at_{session.id}"


def _step_key(session: Session) -> str:
    return f"raup_step_{session.id}"


def _get_elapsed_seconds(session: Session) -> float:
    key = _started_at_key(session)
    if key not in st.session_state:
        st.session_state[key] = time.time()
    return time.time() - st.session_state[key]


def _get_or_compute_step(
    session: Session, answer_repo: AnswerRepository, llm_client: LLMClient, elapsed_seconds: float
) -> QuestionnaireStep:
    key = _step_key(session)
    if key not in st.session_state:
        previous_answers = answer_repo.list_by_session(session.id)
        spinner_text = (
            "Preparando la primera pregunta... la primera vez puede tardar unos minutos."
            if not previous_answers
            else "Preparando la siguiente pregunta..."
        )
        with st.spinner(spinner_text):
            st.session_state[key] = get_next_step(llm_client, session, previous_answers, elapsed_seconds)
    return st.session_state[key]


def _clear_step(session: Session) -> None:
    st.session_state.pop(_step_key(session), None)


def _finish_questionnaire(
    session: Session,
    session_repo: SessionRepository,
    answer_repo: AnswerRepository,
    report_repo: ReportRepository,
    llm_client: LLMClient,
) -> None:
    session_repo.update_status(session.id, SessionStatus.COMPLETED)
    _clear_step(session)

    generated_key = f"raup_report_generated_{session.id}"
    if st.session_state.get(generated_key):
        return  # already generated this browser session — don't regenerate on every rerun

    with st.spinner("Preparando el resumen para tu profesional..."):
        try:
            answers = answer_repo.list_by_session(session.id)
            report = generate_report(llm_client, session, answers)
            report_repo.save(report)
        except Exception:
            # the patient still sees "thank you" even if report generation
            # fails — the clinician's lookup screen shows a clear fallback
            # message and the raw transcript is never lost (it's already saved)
            pass
    st.session_state[generated_key] = True


def _show_question(session: Session, step: QuestionnaireStep, answer_repo: AnswerRepository) -> None:
    st.subheader(step.question)

    # the question number is folded into the widget keys below so each new
    # question gets a fresh, empty widget — otherwise Streamlit keeps
    # reusing the same widget identity across reruns and the answer box
    # keeps showing the previous answer instead of clearing.
    question_number = len(answer_repo.list_by_session(session.id)) + 1

    if step.question_type == "YES_NO":
        col_yes, col_no = st.columns(2)
        if col_yes.button("Sí", key=f"raup_yes_{session.id}_{question_number}", use_container_width=True):
            _save_answer(session, step, "Sí", answer_repo)
        if col_no.button("No", key=f"raup_no_{session.id}_{question_number}", use_container_width=True):
            _save_answer(session, step, "No", answer_repo)
    else:
        with st.form(f"raup_answer_form_{session.id}_{question_number}"):
            answer_text = st.text_area(
                "Tu respuesta",
                label_visibility="collapsed",
                key=f"raup_answer_text_{session.id}_{question_number}",
            )
            submitted = st.form_submit_button("Siguiente")
        if submitted and answer_text.strip():
            _save_answer(session, step, answer_text.strip(), answer_repo)


def _save_answer(session: Session, step: QuestionnaireStep, answer_text: str, answer_repo: AnswerRepository) -> None:
    existing = answer_repo.list_by_session(session.id)

    # Idempotency guard (see D-025): the same question can't be answered twice
    # in a row. A live test produced two identical Q&A rows, typo included —
    # a double-submit (a second click or a resend while the model is still
    # thinking), not two separate answers. Skip the write, keep the flow moving.
    already_answered = bool(existing) and existing[-1].question == step.question
    if not already_answered:
        answer_repo.add(
            Answer(session_id=session.id, order=len(existing) + 1, question=step.question, answer=answer_text)
        )
    _clear_step(session)
    st.rerun()


def _show_document_upload(document_repo: DocumentRepository, session_id: str) -> None:
    counter_key = f"raup_upload_counter_{session_id}"
    counter = st.session_state.get(counter_key, 0)

    with st.expander("📎 Adjuntar un documento (opcional)"):
        uploaded = st.file_uploader(
            "Sube un informe, analítica u otro documento relevante",
            key=f"raup_uploader_{session_id}_{counter}",
        )
        if uploaded is not None:
            storage_path = document_repo.upload_file(session_id, uploaded.name, uploaded.getvalue(), uploaded.type)
            document_repo.add_metadata(
                DocumentMetadata(
                    session_id=session_id,
                    file_name=uploaded.name,
                    storage_path=storage_path,
                    mime_type=uploaded.type,
                    size_bytes=uploaded.size,
                )
            )
            st.session_state[counter_key] = counter + 1
            st.success(f"Documento «{uploaded.name}» subido correctamente.")
            st.rerun()
