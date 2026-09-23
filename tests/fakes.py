"""In-memory repository doubles, for tests only.

Implement the same contracts as raup/repository/base.py. Not for use in the
real app (the MVP's goal is cloud-first with Supabase, see DECISIONS.md
D-006) — this exists purely to test business logic without needing real
Supabase credentials.
"""

from __future__ import annotations

from typing import Optional

from raup.llm.base import LLMClient
from raup.models import Answer, DocumentMetadata, Report, Session, SessionStatus
from raup.repository.base import (
    AnswerRepository,
    DocumentRepository,
    ReportRepository,
    SessionRepository,
)


class InMemorySessionRepository(SessionRepository):
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self, session: Session) -> Session:
        if any(s.code == session.code for s in self._sessions.values()):
            raise ValueError(f"A session with code {session.code} already exists")
        self._sessions[session.id] = session
        return session

    def get_by_code(self, code: str) -> Optional[Session]:
        return next((s for s in self._sessions.values() if s.code == code), None)

    def get_by_id(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].status = status


class InMemoryAnswerRepository(AnswerRepository):
    def __init__(self):
        self._answers: list[Answer] = []

    def add(self, answer: Answer) -> Answer:
        self._answers.append(answer)
        return answer

    def list_by_session(self, session_id: str) -> list[Answer]:
        return sorted(
            (a for a in self._answers if a.session_id == session_id),
            key=lambda a: a.order,
        )


class InMemoryDocumentRepository(DocumentRepository):
    def __init__(self):
        self._documents: list[DocumentMetadata] = []
        self.uploaded_files: dict[str, bytes] = {}  # storage_path -> content

    def upload_file(self, session_id: str, file_name: str, content: bytes, mime_type: Optional[str]) -> str:
        storage_path = f"{session_id}/{file_name}"
        self.uploaded_files[storage_path] = content
        return storage_path

    def add_metadata(self, document: DocumentMetadata) -> DocumentMetadata:
        self._documents.append(document)
        return document

    def list_by_session(self, session_id: str) -> list[DocumentMetadata]:
        return [d for d in self._documents if d.session_id == session_id]


class InMemoryReportRepository(ReportRepository):
    def __init__(self):
        self._reports: dict[str, Report] = {}

    def save(self, report: Report) -> Report:
        self._reports[report.session_id] = report
        return report

    def get_by_session(self, session_id: str) -> Optional[Report]:
        return self._reports.get(session_id)


class FakeLLMClient(LLMClient):
    """Returns pre-scripted responses in order, one per call to `complete`.
    Records every call so tests can assert on what was sent (e.g. that the
    safety preamble was actually included)."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []  # (system_prompt, user_prompt)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if not self._responses:
            raise AssertionError("FakeLLMClient ran out of scripted responses")
        return self._responses.pop(0)
