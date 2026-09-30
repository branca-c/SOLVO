from datetime import datetime

from pydantic import BaseModel


class TelegramBindingLinkResponse(BaseModel):
    url: str
    expires_at: datetime
    telegram_linked: bool


class TelegramBindingStatusResponse(BaseModel):
    telegram_linked: bool
