"""Helper script to test raup.ui.professional with AppTest, no real Supabase.

The in-memory repos live in st.session_state so they persist across the
different `.run()` calls of a single AppTest, just like the real Supabase
connection persists across reruns of the actual app.
"""

import streamlit as st

from raup.ui.professional import show_professional_page
from tests.fakes import InMemoryAnswerRepository, InMemoryReportRepository, InMemorySessionRepository

if "session_repo" not in st.session_state:
    st.session_state["session_repo"] = InMemorySessionRepository()
if "answer_repo" not in st.session_state:
    st.session_state["answer_repo"] = InMemoryAnswerRepository()
if "report_repo" not in st.session_state:
    st.session_state["report_repo"] = InMemoryReportRepository()

show_professional_page(
    st.session_state["session_repo"],
    st.session_state["answer_repo"],
    st.session_state["report_repo"],
)
