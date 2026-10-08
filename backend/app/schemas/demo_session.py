from datetime import datetime

from pydantic import BaseModel


class DemoSessionResponse(BaseModel):
    enabled: bool = True
    session_token: str | None = None
    expires_at: datetime | None = None
    telegram_linked: bool = False


class DemoSessionStatusResponse(BaseModel):
    enabled: bool = True
    expires_at: datetime | None = None
    telegram_linked: bool = False
