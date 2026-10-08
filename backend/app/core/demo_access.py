"""Small shared-key access gate for the public SOLVO demo.

This is intentionally not an identity or authorization system.  It prevents the
normal demo console APIs from being anonymously usable while preserving the
separately authenticated technician and Telegram entry points.
"""

import hmac
from contextvars import ContextVar

from app.core.config import Settings

DEMO_ACCESS_HEADER = "X-SOLVO-DEMO-KEY"
DEMO_SESSION_HEADER = "X-SOLVO-DEMO-SESSION"
DEMO_SESSION_GENERATION_INFO = "solvo_demo_session_generation"

demo_session_generation: ContextVar[int | None] = ContextVar(
    "demo_session_generation", default=None
)
demo_session_write_fence: ContextVar[bool] = ContextVar(
    "demo_session_write_fence", default=False
)


def is_public_api_path(path: str) -> bool:
    return path.startswith("/api/public/assignments/") or path == "/api/telegram/webhook"


def is_session_exempt_api_path(path: str) -> bool:
    return path == "/api/demo-session/acquire"


def requires_demo_session_write_fence(method: str, path: str) -> bool:
    if method not in {"POST", "PATCH", "DELETE"}:
        return False
    if path.startswith("/api/demo-session") or path.startswith("/api/ai/"):
        return False
    # Notification delivery performs its own two-phase generation fencing so
    # the lifecycle advisory lock is never held across the provider HTTP call.
    if path.startswith("/api/assignments/") and path.endswith("/notify"):
        return False
    return not is_public_api_path(path)


def has_demo_access(submitted_key: str | None, settings: Settings) -> bool:
    """Return false for missing configuration as well as missing/bad credentials."""
    if not settings.solvo_demo_access_enabled and not settings.solvo_demo_session_enabled:
        return True
    configured_key = settings.solvo_demo_access_key.get_secret_value()
    if not configured_key or not submitted_key:
        return False
    return hmac.compare_digest(submitted_key, configured_key)
