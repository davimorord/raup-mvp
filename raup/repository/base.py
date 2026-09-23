"""Repository interfaces.

The rest of the app (screens, report generation) depends only on these
interfaces, never on Supabase directly. This way the implementation can be
swapped (e.g. in tests, with in-memory doubles) without touching business
logic — see CLAUDE.md, process section.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from raup.models import Answer, DocumentMetadata, Report, Session, SessionStatus


class SessionRepository(ABC):
    @abstractmethod
    def create(self, session: Session) -> Session:
        """Persists a new session. `session.code` must be unique."""

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[Session]:
        """Returns the session with that code, or None if it doesn't exist."""

    @abstractmethod
    def get_by_id(self, session_id: str) -> Optional[Session]:
        """Returns the session with that id, or None if it doesn't exist."""

    @abstractmethod
    def update_status(self, session_id: str, status: SessionStatus) -> None:
        """Changes the session's status (e.g. once the questionnaire is done)."""


class AnswerRepository(ABC):
    @abstractmethod
    def add(self, answer: Answer) -> Answer:
        """Stores one answer from the adaptive questionnaire."""

    @abstractmethod
    def list_by_session(self, session_id: str) -> list[Answer]:
        """Returns a session's answers, ordered by `order`."""


class DocumentRepository(ABC):
    @abstractmethod
    def upload_file(self, session_id: str, file_name: str, content: bytes, mime_type: Optional[str]) -> str:
        """Uploads raw bytes to storage, unread and unprocessed. Returns the
        storage path to pass to `add_metadata`."""

    @abstractmethod
    def add_metadata(self, document: DocumentMetadata) -> DocumentMetadata:
        """Stores the metadata for a document already uploaded to Storage."""

    @abstractmethod
    def list_by_session(self, session_id: str) -> list[DocumentMetadata]:
        """Returns the documents attached to a session."""


class ReportRepository(ABC):
    @abstractmethod
    def save(self, report: Report) -> Report:
        """Saves (or overwrites) a session's report. One per session."""

    @abstractmethod
    def get_by_session(self, session_id: str) -> Optional[Report]:
        """Returns a session's report, or None if it hasn't been generated yet."""
