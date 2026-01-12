from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from app.settings import settings


def create_access_token(*, subject: str, expires_minutes: int = 60 * 24) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer)
        if payload.get("typ") != "access":
            return None
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            return None
        return sub
    except Exception:
        return None

