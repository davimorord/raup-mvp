"""Helper script to test raup.ui.patient with AppTest, no real Supabase or LLM.

Repos and the LLM client are injected via st.session_state before `at.run()`
(see tests/test_ui_patient.py) so they persist across reruns, and tests can
script exactly what the "model" says each turn.
"""

import streamlit as st

from raup.ui.patient import show_patient_page
from tests.fakes import (
    FakeLLMClient,
    InMemoryAnswerRepository,
    InMemoryDocumentRepository,
    InMemoryReportRepository,
    InMemorySessionRepository,
)

if "session_repo" not in st.session_state:
    st.session_state["session_repo"] = InMemorySessionRepository()
if "answer_repo" not in st.session_state:
    st.session_state["answer_repo"] = InMemoryAnswerRepository()
if "document_repo" not in st.session_state:
    st.session_state["document_repo"] = InMemoryDocumentRepository()
if "report_repo" not in st.session_state:
    st.session_state["report_repo"] = InMemoryReportRepository()
if "llm_client" not in st.session_state:
    st.session_state["llm_client"] = FakeLLMClient(responses=[])

show_patient_page(
    st.session_state["session_repo"],
    st.session_state["answer_repo"],
    st.session_state["document_repo"],
    st.session_state["report_repo"],
    st.session_state["llm_client"],
    st.session_state.get("test_code", ""),
)
