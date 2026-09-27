from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog, Search, SourceHealth, User


async def get_or_create_user(session: AsyncSession, telegram_id: int, **fields) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id, **fields)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def touch_user(session: AsyncSession, user: User) -> None:
    user.last_seen = datetime.now(timezone.utc)
    await session.commit()


async def count_searches_today(session: AsyncSession, user_id: int) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (await session.scalar(
        select(func.count(Search.id)).where(
            Search.user_id == user_id,
            Search.created_at >= start,
        )
    )) or 0


async def create_search(
    session: AsyncSession, user_id: int, target_type: str, target_value: str
) -> Search:
    s = Search(user_id=user_id, target_type=target_type, target_value=target_value)
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


async def finish_search(
    session,
    search,
    *,
    status,
    sources_checked,
    found,
    errors,
    duration_ms,
    result_json,
):
    search.status = status
    search.sources_checked = sources_checked
    search.found_count = found
    search.error_count = errors
    search.duration_ms = duration_ms
    search.result_json = result_json
    await session.commit()


async def recent_searches(session: AsyncSession, user_id: int, limit: int = 10) -> List[Search]:
    return list((await session.scalars(
        select(Search)
        .where(Search.user_id == user_id)
        .order_by(Search.created_at.desc())
        .limit(limit)
    )).all())


async def audit(session, user_id, action, payload=None):
    session.add(AuditLog(user_id=user_id, action=action, payload=payload))
    await session.commit()


# ---------- админка: пользователи ----------

async def list_users(session: AsyncSession, limit: int = 20, offset: int = 0) -> List[User]:
    return list((await session.scalars(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )).all())


async def count_users(session: AsyncSession) -> int:
    return (await session.scalar(select(func.count(User.id)))) or 0


async def all_user_ids(session: AsyncSession) -> List[int]:
    return list((await session.scalars(select(User.telegram_id))).all())


# ---------- админка: поиски ----------

async def list_searches(session: AsyncSession, limit: int = 20, offset: int = 0) -> List[Search]:
    return list((await session.scalars(
        select(Search).order_by(Search.created_at.desc()).limit(limit).offset(offset)
    )).all())


async def count_searches(session: AsyncSession) -> int:
    return (await session.scalar(select(func.count(Search.id)))) or 0


async def stats_by_type(session: AsyncSession) -> dict:
    rows = await session.execute(
        select(Search.target_type, func.count(Search.id)).group_by(Search.target_type)
    )
    return {t: c for t, c in rows.all()}


async def searches_today(session: AsyncSession) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (await session.scalar(
        select(func.count(Search.id)).where(Search.created_at >= start)
    )) or 0


async def avg_duration_ms(session: AsyncSession) -> int:
    val = await session.scalar(select(func.avg(Search.duration_ms)))
    return int(val or 0)


# ---------- админка: health ----------

async def list_source_health(session: AsyncSession) -> List[SourceHealth]:
    return list((await session.scalars(
        select(SourceHealth).order_by(SourceHealth.source)
    )).all())


async def record_source_health(
    session: AsyncSession,
    source: str,
    *,
    ok: bool,
    timed_out: bool,
    duration_ms: int,
) -> None:
    sh = await session.scalar(select(SourceHealth).where(SourceHealth.source == source))
    if sh is None:
        sh = SourceHealth(source=source)
        session.add(sh)
    now = datetime.now(timezone.utc)
    if ok:
        sh.success_count += 1
        sh.last_success = now
    else:
        sh.error_count += 1
        if timed_out:
            sh.timeout_count += 1
        sh.last_failure = now
    total = sh.success_count + sh.error_count
    sh.avg_response_ms = int(
        (sh.avg_response_ms * (total - 1) + duration_ms) / total
    ) if total else duration_ms
    await session.commit()


# алиас — используется в engine.py
upsert_source_health = record_source_health