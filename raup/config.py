"""Configuration loading (environment variables / Streamlit secrets).

Works in two environments without changing code:
- Local: variables defined in an ".env" file (see .env.example), loaded with
  python-dotenv.
- Streamlit Community Cloud: variables defined as app "secrets" (st.secrets),
  no .env file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit as st
except ImportError:  # streamlit not available, e.g. in tests outside the app
    st = None  # type: ignore[assignment]


class MissingConfigError(RuntimeError):
    """Some environment variable/secret needed to start is missing."""


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    key: str


@dataclass(frozen=True)
class RunPodConfig:
    endpoint_id: str
    api_key: str


def _get_value(name: str) -> Optional[str]:
    if st is not None:
        try:
            if name in st.secrets:
                return str(st.secrets[name])
        except Exception:
            # st.secrets raises if secrets.toml doesn't exist (e.g. locally,
            # unconfigured); fall back to environment variables in that case.
            pass
    return os.environ.get(name)


def load_supabase_config() -> SupabaseConfig:
    url = _get_value("SUPABASE_URL")
    key = _get_value("SUPABASE_KEY")
    if not url or not key:
        raise MissingConfigError(
            "Faltan SUPABASE_URL / SUPABASE_KEY. Copia .env.example a .env y "
            "rellénalas (local), o defínelas como secrets de la app en "
            "Streamlit Community Cloud (producción)."
        )
    return SupabaseConfig(url=url, key=key)


def load_runpod_config() -> RunPodConfig:
    endpoint_id = _get_value("RUNPOD_ENDPOINT_ID")
    api_key = _get_value("RUNPOD_API_KEY")
    if not endpoint_id or not api_key:
        raise MissingConfigError(
            "Faltan RUNPOD_ENDPOINT_ID / RUNPOD_API_KEY. Se configuran en el "
            "Paso 4, al desplegar MedGemma en RunPod Serverless."
        )
    return RunPodConfig(endpoint_id=endpoint_id, api_key=api_key)


def build_patient_link(code: str) -> Optional[str]:
    """Direct link for the patient, if APP_URL has been configured (Step 7:
    once the app is deployed, it's set as a secret in Streamlit Cloud).
    Without APP_URL, the clinician just shares the code by hand."""

    base = _get_value("APP_URL")
    if not base:
        return None
    return f"{base.rstrip('/')}/?code={code}"
