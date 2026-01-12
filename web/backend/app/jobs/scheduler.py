from __future__ import annotations

from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.db.session import engine
from app.jobs.recompute import recompute_market
from app.settings import settings


def start_scheduler() -> AsyncIOScheduler | None:
    if not settings.enable_scheduler:
        return None

    sched = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    async def _run_daily() -> None:
        with Session(engine) as session:
            today = date.today()
            await recompute_market(session=session, market="KR", day=today)
            await recompute_market(session=session, market="US", day=today)

    # Default: 18:10 Asia/Seoul (after KR close; US will just use latest available daily bars)
    trigger = CronTrigger(hour=18, minute=10)
    sched.add_job(_run_daily, trigger=trigger, id="daily_recompute", replace_existing=True)

    sched.start()
    return sched

