"""Repository کارهای «کپی کانال» (`.کپی‌کانال`)."""
import datetime as dt

from sqlalchemy import delete, select, update

from ..db.engine import session_scope
from ..db.models_ext import ChannelCopyJob, ChannelCopyTarget


def _to_dict(r: ChannelCopyJob) -> dict:
    return {
        "id": r.id,
        "source_id": r.source_id,
        "source_title": r.source_title,
        "source_ref": r.source_ref,
        "dest_id": r.dest_id,
        "dest_title": r.dest_title,
        "dest_ref": r.dest_ref,
        "last_id": r.last_id,
        "copied": r.copied,
        "skipped": r.skipped,
        "total_hint": r.total_hint,
        "status": r.status,
        "drop_author": r.drop_author,
        "window_start": r.window_start,
        "window_count": r.window_count,
        "from_date": r.from_date,
        "watch": r.watch,
        "children": r.children,
        "last_error": r.last_error,
    }


async def set_job_meta(job_id: int, *, children: str | None = None, note: str = "") -> None:
    """تنظیمِ ستونِ children (شناسه‌ی کارهای فرزندِ یک کارِ سازمان‌دهنده)."""
    from sqlalchemy import update as _update

    async with session_scope() as session:
        await session.execute(
            _update(ChannelCopyJob).where(ChannelCopyJob.id == job_id).values(children=children or "")
        )


async def list_children(job_id: int) -> list[dict]:
    """کارهای فرزندِ یک کارِ سازمان‌دهنده."""
    async with session_scope() as session:
        parent = await session.get(ChannelCopyJob, job_id)
        if parent is None or not parent.children:
            return []
        ids = [int(x) for x in parent.children.split(",") if x.strip().isdigit()]
        if not ids:
            return []
        rows = (
            await session.execute(select(ChannelCopyJob).where(ChannelCopyJob.id.in_(ids)))
        ).scalars().all()
        return [_to_dict(r) for r in rows]


async def create_job(
    *,
    source_id: int,
    source_title: str,
    source_ref: str,
    dest_id: int,
    dest_title: str,
    dest_ref: str,
    last_id: int = 0,
    total_hint: int = 0,
    drop_author: bool = True,
    from_date: dt.datetime | None = None,
    watch: bool = False,
) -> dict:
    async with session_scope() as session:
        obj = ChannelCopyJob(
            source_id=source_id,
            source_title=source_title,
            source_ref=source_ref,
            dest_id=dest_id,
            dest_title=dest_title,
            dest_ref=dest_ref,
            last_id=last_id,
            total_hint=total_hint,
            drop_author=drop_author,
            from_date=from_date,
            watch=watch,
            status="running",
        )
        session.add(obj)
        await session.flush()
        return _to_dict(obj)


async def get_job(job_id: int) -> dict | None:
    async with session_scope() as session:
        r = await session.get(ChannelCopyJob, job_id)
        return _to_dict(r) if r else None


async def get_latest_job() -> dict | None:
    async with session_scope() as session:
        r = (
            await session.execute(select(ChannelCopyJob).order_by(ChannelCopyJob.id.desc()).limit(1))
        ).scalar_one_or_none()
        return _to_dict(r) if r else None


async def list_jobs(limit: int = 10) -> list[dict]:
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(ChannelCopyJob).order_by(ChannelCopyJob.id.desc()).limit(limit)
            )
        ).scalars().all()
        return [_to_dict(r) for r in rows]


async def update_progress(
    job_id: int,
    *,
    last_id: int,
    copied: int,
    skipped: int,
    window_start: dt.datetime | None,
    window_count: int,
) -> None:
    async with session_scope() as session:
        await session.execute(
            update(ChannelCopyJob)
            .where(ChannelCopyJob.id == job_id)
            .values(
                last_id=last_id,
                copied=copied,
                skipped=skipped,
                window_start=window_start,
                window_count=window_count,
            )
        )


async def set_status(job_id: int, status: str, error: str = "") -> None:
    async with session_scope() as session:
        await session.execute(
            update(ChannelCopyJob)
            .where(ChannelCopyJob.id == job_id)
            .values(status=status, last_error=error[:1000])
        )


async def set_total_hint(job_id: int, total: int) -> None:
    async with session_scope() as session:
        await session.execute(
            update(ChannelCopyJob).where(ChannelCopyJob.id == job_id).values(total_hint=total)
        )


async def mark_running_as_paused() -> int:
    """بعد از ری‌استارتِ پروسه: کارهای «running» دیگه تسکِ زنده ندارن؛ به paused می‌رن."""
    async with session_scope() as session:
        res = await session.execute(
            update(ChannelCopyJob)
            .where(ChannelCopyJob.status == "running")
            .values(status="paused", last_error="پروسه ری‌استارت شد؛ با «ادامه» دنبال کن")
        )
        return res.rowcount or 0


async def delete_job(job_id: int) -> bool:
    async with session_scope() as session:
        res = await session.execute(delete(ChannelCopyJob).where(ChannelCopyJob.id == job_id))
        return bool(res.rowcount)


# --------------------------------------------------- نام‌های مقصد ---
def _target_dict(r: ChannelCopyTarget) -> dict:
    return {"id": r.id, "name": r.name, "chat_id": r.chat_id, "title": r.title}


async def save_target(name: str, chat_id: int, title: str = "") -> dict:
    """اسم → کانال (اسمِ تکراری، آدرسش به‌روز می‌شه)."""
    name = (name or "").strip()
    async with session_scope() as session:
        r = (
            await session.execute(select(ChannelCopyTarget).where(ChannelCopyTarget.name == name))
        ).scalar_one_or_none()
        if r is None:
            r = ChannelCopyTarget(name=name, chat_id=chat_id, title=title)
            session.add(r)
        else:
            r.chat_id, r.title = chat_id, title
        await session.flush()
        return _target_dict(r)


async def get_target(name: str) -> dict | None:
    name = (name or "").strip()
    async with session_scope() as session:
        r = (
            await session.execute(select(ChannelCopyTarget).where(ChannelCopyTarget.name == name))
        ).scalar_one_or_none()
        return _target_dict(r) if r else None


async def list_targets() -> list[dict]:
    async with session_scope() as session:
        rows = (
            await session.execute(select(ChannelCopyTarget).order_by(ChannelCopyTarget.name))
        ).scalars().all()
        return [_target_dict(r) for r in rows]


async def delete_target(name: str) -> bool:
    name = (name or "").strip()
    async with session_scope() as session:
        res = await session.execute(delete(ChannelCopyTarget).where(ChannelCopyTarget.name == name))
        return bool(res.rowcount)


async def last_progress(source_id: int, dest_id: int) -> tuple[int, int | None]:
    """(last_id, from_date-ish) از جدیدترین کارِ همین جفت‌کانال — برای ادامه‌ی خودکار."""
    async with session_scope() as session:
        r = (
            await session.execute(
                select(ChannelCopyJob)
                .where(
                    ChannelCopyJob.source_id == source_id,
                    ChannelCopyJob.dest_id == dest_id,
                )
                .order_by(ChannelCopyJob.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return (r.last_id, r.id) if r else (0, None)
