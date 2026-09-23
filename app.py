"""RaUP app entry point.

Routes based on the `code` URL parameter:
- no `code`: clinician screen (create sessions, look up reports).
- with `code`: patient screen (adaptive pre-visit questionnaire).

No login (out of scope for the MVP, see CLAUDE.md): the clinician/patient
distinction is made purely by that query param.
"""

import streamlit as st

from raup.config import MissingConfigError
from raup.llm.medgemma_client import MedGemmaClient
from raup.repository.supabase_repo import (
    SupabaseAnswerRepository,
    SupabaseDocumentRepository,
    SupabaseReportRepository,
    SupabaseSessionRepository,
    create_supabase_client,
)
from raup.ui.patient import show_patient_page
from raup.ui.professional import show_professional_page

st.set_page_config(page_title="RaUP", page_icon="🩺")


@st.cache_resource
def _supabase_client():
    return create_supabase_client()


try:
    client = _supabase_client()
except MissingConfigError as error:
    st.warning(str(error))
    st.stop()
except Exception as error:  # wrong URL, tables not created, no network, etc.
    st.error(
        "No se pudo conectar con Supabase. Revisa la configuración y que hayas "
        "ejecutado supabase/schema.sql."
    )
    st.exception(error)
    st.stop()

session_repo = SupabaseSessionRepository(client)
answer_repo = SupabaseAnswerRepository(client)
report_repo = SupabaseReportRepository(client)

code = st.query_params.get("code")
if code:
    try:
        llm_client = MedGemmaClient()
    except MissingConfigError as error:
        st.warning(str(error))
        st.stop()
    document_repo = SupabaseDocumentRepository(client)
    show_patient_page(session_repo, answer_repo, document_repo, report_repo, llm_client, code)
else:
    show_professional_page(session_repo, answer_repo, report_repo)
