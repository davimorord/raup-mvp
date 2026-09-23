"""MedGemma client via RunPod Serverless.

VERIFIED against the live endpoint on 2026-09-23 (see D-017). Two corrections
from the original draft contract:
- Sampling params go under `input.sampling_params`, not flat in `input`.
- `/run` (async) is used instead of `/runsync`: a cold start took ~256s in
  testing, well past the ~100s edge timeout RunPod's sync routes sit behind
  (they respond with a Cloudflare 524 past that). `/run` returns a job id
  immediately; this client polls `/status/{job_id}` until a terminal state.
- The completion is `output[0].choices[0].message.content` — `output` is a
  list, not a single object.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

from raup.config import load_runpod_config
from raup.llm.base import LLMClient

_RUNPOD_BASE_URL = "https://api.runpod.ai/v2"
_REQUEST_TIMEOUT_SECONDS = 30  # for each individual HTTP call, not the whole job
_POLL_INTERVAL_SECONDS = 3
_MAX_WAIT_SECONDS = 420  # generous: observed cold start ~256s (see D-017)
_MAX_TOKENS = 512
_TEMPERATURE = 0.3  # low: this is data collection, not creative writing

_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}


class MedGemmaClient(LLMClient):
    def __init__(self, endpoint_id: Optional[str] = None, api_key: Optional[str] = None):
        if endpoint_id is None or api_key is None:
            config = load_runpod_config()
            endpoint_id = endpoint_id or config.endpoint_id
            api_key = api_key or config.api_key
        self._endpoint_id = endpoint_id
        self._api_key = api_key

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        job_id = self._submit(system_prompt, user_prompt)
        result = self._wait_for_result(job_id)
        return result["output"][0]["choices"][0]["message"]["content"].strip()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _submit(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{_RUNPOD_BASE_URL}/{self._endpoint_id}/run"
        payload = {
            "input": {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "sampling_params": {
                    "max_tokens": _MAX_TOKENS,
                    "temperature": _TEMPERATURE,
                },
            }
        }
        response = requests.post(
            url, json=payload, headers=self._headers(), timeout=_REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return response.json()["id"]

    def _wait_for_result(self, job_id: str) -> dict:
        url = f"{_RUNPOD_BASE_URL}/{self._endpoint_id}/status/{job_id}"
        deadline = time.monotonic() + _MAX_WAIT_SECONDS

        while True:
            response = requests.get(url, headers=self._headers(), timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            body = response.json()
            status = body.get("status")

            if status == "COMPLETED":
                return body
            if status in _TERMINAL_STATUSES:
                raise RuntimeError(f"MedGemma job {job_id} ended as {status}: {body.get('error')}")
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"MedGemma job {job_id} did not complete within {_MAX_WAIT_SECONDS}s "
                    f"(last status: {status})"
                )
            time.sleep(_POLL_INTERVAL_SECONDS)
