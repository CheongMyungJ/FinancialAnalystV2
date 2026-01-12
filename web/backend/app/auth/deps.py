from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException

from app.auth.jwt import verify_access_token
from app.settings import settings


def require_admin(access_token: str | None = Cookie(default=None)) -> str:
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sub = verify_access_token(access_token)
    if sub != settings.admin_username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return sub

