"""Runtime configuration, entirely environment driven.

The app must run in two modes:

* ``memory``  - a single-process, in-memory store. Used for local development
  and the test suite. No external services required.
* ``firebase`` - Firebase Realtime Database via the Admin SDK. Used in
  production (Vercel). The store survives serverless instance churn because it
  lives outside the process.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

try:  # local convenience; on Vercel env vars are provided directly.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

SESSION_COOKIE = "pfd_session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.store_backend = (os.environ.get("PFD_STORE") or "").strip().lower()
        self.firebase_database_url = (os.environ.get("FIREBASE_DATABASE_URL") or "").strip().rstrip("/")
        self.firebase_service_account = (os.environ.get("FIREBASE_SERVICE_ACCOUNT") or "").strip()
        self.google_application_credentials = (
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or ""
        ).strip()
        self.firebase_web_config_raw = (os.environ.get("FIREBASE_WEB_CONFIG") or "").strip()
        try:
            self.room_ttl_seconds = int(os.environ.get("ROOM_TTL_SECONDS") or 2 * 60 * 60)
        except ValueError:
            self.room_ttl_seconds = 2 * 60 * 60
        self.cookie_secure = _as_bool(os.environ.get("COOKIE_SECURE"), default=False)

    # -- store selection -------------------------------------------------
    def resolved_store_backend(self) -> str:
        if self.store_backend in ("memory", "firebase"):
            return self.store_backend
        if self.firebase_database_url and (
            self.firebase_service_account or self.google_application_credentials
        ):
            return "firebase"
        return "memory"

    def has_firebase_admin_credentials(self) -> bool:
        return bool(self.firebase_service_account or self.google_application_credentials)

    # -- client (browser) firebase config --------------------------------
    def web_firebase_config(self) -> Dict[str, Any]:
        if self.firebase_web_config_raw:
            try:
                parsed = json.loads(self.firebase_web_config_raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}
        if self.firebase_database_url:
            # A ``databaseURL`` alone is enough for unauthenticated RTDB reads
            # (which is all the browser needs: the revision counter).
            return {"databaseURL": self.firebase_database_url}
        return {}


settings = Settings()


__all__ = ["Settings", "settings", "SESSION_COOKIE", "SESSION_MAX_AGE_SECONDS"]
