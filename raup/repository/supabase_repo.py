"""Repository implementation on top of Supabase (Postgres + PostgREST).

See raup/repository/base.py for the contract implemented here, and
supabase/schema.sql for the corresponding tables. Table names and column
keys below are kept in Spanish on purpose: they must match the live
Supabase schema (see DECISIONS.md D-013).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from supabase import Client, create_client

from raup.config import load_supabase_config
from raup.models import (
    Alert,
    ConsultationMode,
    DEFAULT_SPECIALTY,
    DocumentMetadata,
    Answer,
    Report,
    Session,
    SessionStatus,
)
from raup.repository.base import (
    AnswerRepository,
    DocumentRepository,
    ReportRepository,
    SessionRepository,
)


def create_supabase_client() -> Client:
    """Builds the Supabase client from configuration (.env or secrets)."""

    config = load_supabase_config()
    return create_client(config.url, config.key)


def _to_iso(moment: Optional[datetime]) -> Optional[str]:
    return moment.isoformat() if moment else None


def _from_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _new_upload_id() -> str:
    return uuid.uuid4().hex[:8]


class SupabaseSessionRepository(SessionRepository):
    _TABLE = "sesiones"

    def __init__(self, client: Client):
        self._client = client

    def create(self, session: Session) -> Session:
        row = {
            "id": session.id,
            "codigo": session.code,
            "modo": session.mode.value,
            "especialidad": session.specialty,
            "motivo_consulta": session.consultation_reason,
            "estado": session.status.value,
            "creado_en": _to_iso(session.created_at),
            "completado_en": _to_iso(session.completed_at),
        }
        self._client.table(self._TABLE).insert(row).execute()
        return session

    def get_by_code(self, code: str) -> Optional[Session]:
        result = (
            self._client.table(self._TABLE)
            .select("*")
            .eq("codigo", code)
            .limit(1)
            .execute()
        )
        return self._first_row_to_session(result.data)

    def get_by_id(self, session_id: str) -> Optional[Session]:
        result = (
            self._client.table(self._TABLE)
            .select("*")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        return self._first_row_to_session(result.data)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        data: dict[str, Any] = {"estado": status.value}
        if status == SessionStatus.COMPLETED:
            data["completado_en"] = _to_iso(datetime.utcnow())
        self._client.table(self._TABLE).update(data).eq("id", session_id).execute()

    @staticmethod
    def _first_row_to_session(rows: list[dict]) -> Optional[Session]:
        if not rows:
            return None
        row = rows[0]
        return Session(
            id=row["id"],
            code=row["codigo"],
            mode=ConsultationMode(row["modo"]),
            specialty=row.get("especialidad", DEFAULT_SPECIALTY),
            consultation_reason=row.get("motivo_consulta"),
            status=SessionStatus(row["estado"]),
            created_at=_from_iso(row["creado_en"]),
            completed_at=_from_iso(row.get("completado_en")),
        )


class SupabaseAnswerRepository(AnswerRepository):
    _TABLE = "respuestas"

    def __init__(self, client: Client):
        self._client = client

    def add(self, answer: Answer) -> Answer:
        row = {
            "id": answer.id,
            "sesion_id": answer.session_id,
            "orden": answer.order,
            "pregunta": answer.question,
            "respuesta": answer.answer,
            "creado_en": _to_iso(answer.created_at),
        }
        self._client.table(self._TABLE).insert(row).execute()
        return answer

    def list_by_session(self, session_id: str) -> list[Answer]:
        result = (
            self._client.table(self._TABLE)
            .select("*")
            .eq("sesion_id", session_id)
            .order("orden")
            .execute()
        )
        return [
            Answer(
                id=row["id"],
                session_id=row["sesion_id"],
                order=row["orden"],
                question=row["pregunta"],
                answer=row["respuesta"],
                created_at=_from_iso(row["creado_en"]),
            )
            for row in result.data
        ]


class SupabaseDocumentRepository(DocumentRepository):
    _TABLE = "documentos"
    _BUCKET = "documentos"

    def __init__(self, client: Client):
        self._client = client

    def upload_file(self, session_id: str, file_name: str, content: bytes, mime_type: Optional[str]) -> str:
        """Uploads raw bytes to Supabase Storage (bucket "documentos") and
        returns the storage path. The file is stored as-is, never read or
        processed — see raup/models.py DocumentMetadata."""

        storage_path = f"{session_id}/{_new_upload_id()}-{file_name}"
        self._client.storage.from_(self._BUCKET).upload(
            storage_path,
            content,
            file_options={"content-type": mime_type} if mime_type else None,
        )
        return storage_path

    def add_metadata(self, document: DocumentMetadata) -> DocumentMetadata:
        row = {
            "id": document.id,
            "sesion_id": document.session_id,
            "nombre_archivo": document.file_name,
            "ruta_storage": document.storage_path,
            "tipo_mime": document.mime_type,
            "tamano_bytes": document.size_bytes,
            "subido_en": _to_iso(document.uploaded_at),
        }
        self._client.table(self._TABLE).insert(row).execute()
        return document

    def list_by_session(self, session_id: str) -> list[DocumentMetadata]:
        result = (
            self._client.table(self._TABLE)
            .select("*")
            .eq("sesion_id", session_id)
            .execute()
        )
        return [
            DocumentMetadata(
                id=row["id"],
                session_id=row["sesion_id"],
                file_name=row["nombre_archivo"],
                storage_path=row["ruta_storage"],
                mime_type=row.get("tipo_mime"),
                size_bytes=row.get("tamano_bytes"),
                uploaded_at=_from_iso(row["subido_en"]),
            )
            for row in result.data
        ]


class SupabaseReportRepository(ReportRepository):
    _TABLE = "informes"

    def __init__(self, client: Client):
        self._client = client

    def save(self, report: Report) -> Report:
        row = {
            "id": report.id,
            "sesion_id": report.session_id,
            "resumen_ejecutivo": report.executive_summary,
            "alertas": [alert.__dict__ for alert in report.alerts],
            "areas_a_profundizar": report.areas_to_explore,
            "generado_en": _to_iso(report.generated_at),
        }
        self._client.table(self._TABLE).upsert(row, on_conflict="sesion_id").execute()
        return report

    def get_by_session(self, session_id: str) -> Optional[Report]:
        result = (
            self._client.table(self._TABLE)
            .select("*")
            .eq("sesion_id", session_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        return Report(
            id=row["id"],
            session_id=row["sesion_id"],
            executive_summary=row["resumen_ejecutivo"],
            alerts=[Alert(**alert) for alert in row.get("alertas", [])],
            areas_to_explore=row.get("areas_a_profundizar", []),
            generated_at=_from_iso(row["generado_en"]),
        )
