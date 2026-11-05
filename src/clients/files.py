# generated from brief/04 · part 04 owns this file
"""Files API upload/delete (part 04 §6, ``skills/meta-api.md``).

``POST {base}/files`` takes multipart fields ``file``,
``purpose=user_data``, ``expires_after[anchor]=created_at`` and
``expires_after[seconds]=3600``; the answer is ``{"id", "bytes",
"created_at", "expires_at", "status"}``. Reference the file as
``{"type": "input_video", "file_id": id}`` and remove it with
``DELETE {base}/files/{id}``. Uploads and deletes cost $0.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config as _config
from src.accounting import FailedCallError

from ._http import RETRYABLE_STATUSES, auth_headers, backoff_s

__all__ = [
    "FilesApi",
    "delete_file",
    "upload_file",
]


def _default_sleep(seconds: float) -> None:
    import time as _time

    _time.sleep(float(seconds))


def upload_file(api_key, base_url, path, *, timeout=None,
                sleep=None) -> dict:
    """Upload one file; return the Files record (with ``id``)."""
    import httpx  # noqa: PLC0415 — the one HTTP library (part 04 §6)

    pause = sleep if sleep is not None else _default_sleep
    limit = float(timeout if timeout is not None
                  else _config.API_TIMEOUT_S)
    base = str(base_url or _config.API_BASE_URL)
    data = Path(str(path)).read_bytes()
    attempts = int(_config.API_MAX_ATTEMPTS)
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(timeout=limit) as client:
                response = client.post(
                    f"{base}/files",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (Path(str(path)).name, data,
                                    "video/mp4")},
                    data={"purpose": "user_data",
                          "expires_after[anchor]": "created_at",
                          "expires_after[seconds]": "3600"})
        except Exception as exc:  # noqa: BLE001 — transport death
            last = exc
            if attempt < attempts:
                pause(backoff_s(attempt))
            continue
        status = int(response.status_code)
        if status in RETRYABLE_STATUSES:
            last = ValueError(f"HTTP {status}")
            if attempt < attempts:
                pause(backoff_s(attempt))
            continue
        if 200 <= status < 300:
            try:
                record = json.loads(response.content.decode(
                    "utf-8", "replace"))
            except ValueError as exc:
                raise FailedCallError(
                    "Files upload returned no JSON record") from exc
            if not isinstance(record, dict) or not record.get("id"):
                raise FailedCallError(
                    "Files upload returned no file id")
            return record
        if 400 <= status < 500:
            raise FailedCallError(
                f"Files upload HTTP {status}: "
                f"{response.content.decode('utf-8', 'replace')[:300]}")
        last = ValueError(f"HTTP {status}")
        if attempt < attempts:
            pause(backoff_s(attempt))
    from src.accounting import NetworkError  # noqa: PLC0415 — exhausted

    raise NetworkError(f"Files upload failed after {attempts} "
                       f"attempts: {last}")


def delete_file(api_key, base_url, file_id, *, timeout=None) -> bool:
    """Delete one uploaded file. A failed delete is ignored (``False``).

    ``skills/sam-3-1.md``: the SAM file is always deleted afterwards;
    a failed delete never fails the call.
    """
    import httpx  # noqa: PLC0415 — the one HTTP library (part 04 §6)

    limit = float(timeout if timeout is not None
                  else _config.API_TIMEOUT_S)
    base = str(base_url or _config.API_BASE_URL)
    try:
        with httpx.Client(timeout=limit) as client:
            response = client.delete(
                f"{base}/files/{file_id}",
                headers={"Authorization": f"Bearer {api_key}"})
        return 200 <= int(response.status_code) < 300
    except Exception:  # noqa: BLE001 — ignored by contract
        return False


class FilesApi:
    """Upload/delete bound to one key (``build_clients()["files"]``)."""

    def __init__(self, api_key, *, base_url=None, timeout=None,
                 sleep=None):
        self._key = str(api_key)
        self._base = str(base_url or _config.API_BASE_URL)
        self._timeout = float(timeout if timeout is not None
                              else _config.API_TIMEOUT_S)
        self._sleep = sleep

    def upload(self, path) -> dict:
        """Upload ``path``; return the Files record."""
        return upload_file(self._key, self._base, path,
                           timeout=self._timeout, sleep=self._sleep)

    def delete(self, file_id) -> bool:
        """Delete ``file_id``; ``False`` when the delete failed."""
        return delete_file(self._key, self._base, file_id,
                           timeout=self._timeout)

    @property
    def headers(self) -> dict:
        """Auth headers (for tests asserting the key's placement)."""
        return auth_headers(self._key)
