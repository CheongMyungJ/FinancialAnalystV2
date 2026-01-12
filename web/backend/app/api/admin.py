from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_admin
from app.auth.jwt import create_access_token
from app.db.init_db import seed_default_factors, seed_default_weight_presets
from app.db.models import FactorDefinition, JobLog, WeightPreset
from app.db.session import engine, get_session
from app.jobs.recompute import recompute_market
from app.settings import settings
import json

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/health")
def admin_health() -> dict:
    return {"status": "ok"}


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(req: LoginRequest, response: Response) -> dict:
    if req.username != settings.admin_username or req.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=settings.admin_username)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=60 * 60 * 24,
        path="/",
    )
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(admin: str = Depends(require_admin)) -> dict:
    return {"username": admin}


class FactorUpsert(BaseModel):
    key: str
    name: str
    description: str | None = None
    factor_type: str
    calculator: str
    weight: float
    higher_is_better: bool
    normalize: str = "percentile"
    enabled: bool = True


@router.get("/factors")
def list_factors(
    admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    seed_default_factors(session)
    seed_default_weight_presets(session)
    rows = session.exec(select(FactorDefinition).order_by(FactorDefinition.key.asc())).all()
    return {
        "items": [
            {
                "id": r.id,
                "key": r.key,
                "name": r.name,
                "description": r.description,
                "factor_type": r.factor_type,
                "calculator": r.calculator,
                "weight": r.weight,
                "higher_is_better": r.higher_is_better,
                "normalize": r.normalize,
                "enabled": r.enabled,
            }
            for r in rows
        ]
    }


@router.get("/presets")
def list_presets(
    admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    seed_default_weight_presets(session)
    rows = session.exec(select(WeightPreset).order_by(WeightPreset.key.asc())).all()
    return {
        "items": [
            {
                "key": r.key,
                "name": r.name,
                "description": r.description,
            }
            for r in rows
        ]
    }


class ApplyPresetRequest(BaseModel):
    preset_key: str


@router.post("/presets/apply")
def apply_preset(
    body: ApplyPresetRequest,
    admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    seed_default_factors(session)
    seed_default_weight_presets(session)
    preset = session.exec(select(WeightPreset).where(WeightPreset.key == body.preset_key)).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    try:
        cfg = json.loads(preset.config_json)
    except Exception:
        raise HTTPException(status_code=500, detail="Preset config_json is invalid")

    weights: dict[str, float] = cfg.get("weights") or {}
    enabled_map: dict[str, bool] = cfg.get("enabled") or {}
    mode = (cfg.get("mode") or "strict").lower()
    if not isinstance(weights, dict) or not isinstance(enabled_map, dict):
        raise HTTPException(status_code=500, detail="Preset config schema invalid")

    rows = session.exec(select(FactorDefinition)).all()
    by_key = {r.key: r for r in rows}

    # strict: disable anything not in preset
    if mode == "strict":
        for r in rows:
            r.enabled = False
            r.weight = 0.0
            session.add(r)

    # apply preset values
    for k, w in weights.items():
        row = by_key.get(k)
        if not row:
            continue
        try:
            row.weight = float(w)
        except Exception:
            continue
        row.enabled = bool(enabled_map.get(k, True))
        session.add(row)

    # normalize weights across enabled factors (only those present in preset when strict; otherwise across enabled overall)
    enabled_rows = [r for r in rows if r.enabled]
    s = sum(float(r.weight) for r in enabled_rows if r.weight is not None)
    if s > 0:
        for r in enabled_rows:
            r.weight = float(r.weight) / s
            session.add(r)

    session.commit()
    return {"ok": True, "applied": preset.key, "mode": mode}


@router.post("/factors")
def create_factor(
    body: FactorUpsert,
    admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    exists = session.exec(select(FactorDefinition).where(FactorDefinition.key == body.key)).first()
    if exists:
        raise HTTPException(status_code=409, detail="Factor key already exists")
    row = FactorDefinition(**body.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"id": row.id}


@router.put("/factors/{factor_id}")
def update_factor(
    factor_id: int,
    body: FactorUpsert,
    admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    row = session.get(FactorDefinition, factor_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    return {"ok": True}


@router.delete("/factors/{factor_id}")
def delete_factor(
    factor_id: int,
    admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    row = session.get(FactorDefinition, factor_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    session.delete(row)
    session.commit()
    return {"ok": True}


class RecomputeRequest(BaseModel):
    market: str  # KR / US / ALL
    day: date | None = None


@router.post("/jobs/recompute")
async def trigger_recompute(
    body: RecomputeRequest,
    admin: str = Depends(require_admin),
) -> dict:
    d = body.day or date.today()
    m = body.market.upper()
    if m not in ("KR", "US", "ALL"):
        raise HTTPException(status_code=400, detail="market must be KR|US|ALL")

    async def _run(market: str) -> None:
        with Session(engine) as session:
            await recompute_market(session=session, market=market, day=d)  # type: ignore[arg-type]

    if m == "ALL":
        asyncio.create_task(_run("KR"))
        asyncio.create_task(_run("US"))
    else:
        asyncio.create_task(_run(m))
    return {"ok": True, "scheduled": True, "day": d.isoformat(), "market": m}


@router.get("/jobs/logs")
def job_logs(
    admin: str = Depends(require_admin),
    session: Session = Depends(get_session),
    limit: int = 50,
) -> dict:
    rows = session.exec(select(JobLog).order_by(JobLog.started_at.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "id": r.id,
                "job_name": r.job_name,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "message": r.message,
            }
            for r in rows
        ]
    }

