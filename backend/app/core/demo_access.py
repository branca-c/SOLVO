"""Small shared-key access gate for the public SOLVO demo.

This is intentionally not an identity or authorization system.  It prevents the
normal demo console APIs from being anonymously usable while preserving the
separately authenticated technician and Telegram entry points.
"""

import hmac

from app.core.config import Settings

DEMO_ACCESS_HEADER = "X-SOLVO-DEMO-KEY"


def is_public_api_path(path: str) -> bool:
    return path.startswith("/api/public/assignments/") or path == "/api/telegram/webhook"


def has_demo_access(submitted_key: str | None, settings: Settings) -> bool:
    """Return false for missing configuration as well as missing/bad credentials."""
    if not settings.solvo_demo_access_enabled:
        return True
    configured_key = settings.solvo_demo_access_key.get_secret_value()
    if not configured_key or not submitted_key:
        return False
    return hmac.compare_digest(submitted_key, configured_key)
