"""Repository ایندکسِ پیام‌ها (جستجوی معنایی) - جدول message_index.

هیچ Handler‌ای مستقیم SQL نمی‌زنه؛ همه‌چیز از همین توابع می‌گذره. insert روی
PostgreSQL (پروداکشن) و sqlite (تست‌های محلی) هر دو کار می‌کنه.
"""
import datetime as dt
from typing import Iterable, Optional, Sequence

from sqlalchemy import delete, func, or_, select, update

from ..db.engine import engine, session_scope
from ..db.models_ext import MessageIndex


def _insert_ignore_stmt(rows: list[dict]):
    """INSERT ... ON CONFLICT DO NOTHING روی (chat_id, message_id)."""
    if engine.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _insert
    else:
        from sqlalchemy.dialects.postgresql import insert as _insert
    stmt = _insert(MessageIndex).values(rows)
    return stmt.on_conflict_do_nothing(index_elements=["chat_id", "message_id"])


def _like_escape(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def insert_many(rows: list[dict]) -> int:
    """درجِ دسته‌ایِ پیام‌ها؛ ردیف‌های تکراری نادیده گرفته می‌شن. خروجی: تعداد تلاش‌شده."""
    if not rows:
        return 0
    # سقفِ پارامترهای bind در sqlite/psycopg → دسته‌های کوچک
    done = 0
    async with session_scope() as session:
        for i in range(0, len(rows), 100):
            batch = rows[i : i + 100]
            await session.execute(_insert_ignore_stmt(batch))
            done += len(batch)
    return done


async def existing_ids(chat_id: int, message_ids: Sequence[int]) -> set[int]:
    if not message_ids:
        return set()
    async with session_scope() as session:
        res = await session.execute(
            select(MessageIndex.message_id).where(
                MessageIndex.chat_id == chat_id, MessageIndex.message_id.in_(list(message_ids))
            )
        )
        return {r[0] for r in res.all()}


async def count_all() -> int:
    async with session_scope() as session:
        return (await session.execute(select(func.count()).select_from(MessageIndex))).scalar_one()


async def count_embedded(model: Optional[str] = None) -> int:
    async with session_scope() as session:
        q = select(func.count()).select_from(MessageIndex).where(MessageIndex.embedding.is_not(None))
        if model:
            q = q.where(MessageIndex.embed_model == model)
        return (await session.execute(q)).scalar_one()


async def date_range() -> tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    async with session_scope() as session:
        row = (
            await session.execute(select(func.min(MessageIndex.date), func.max(MessageIndex.date)))
        ).one()
        return row[0], row[1]


async def top_chats(limit: int = 8) -> list[tuple[int, Optional[str], int]]:
    """(chat_id, title, تعداد) پرپیام‌ترین چت‌های ایندکس‌شده."""
    async with session_scope() as session:
        res = await session.execute(
            select(MessageIndex.chat_id, func.max(MessageIndex.chat_title), func.count())
            .group_by(MessageIndex.chat_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [(r[0], r[1], r[2]) for r in res.all()]


async def fetch_embeddings(model: str, *, after_id: int = 0, limit: int = 5000):
    """صفحه‌ای: (id, chat_id, date, embedding) برای ساختِ کشِ بردارها."""
    async with session_scope() as session:
        res = await session.execute(
            select(MessageIndex.id, MessageIndex.chat_id, MessageIndex.date, MessageIndex.embedding)
            .where(
                MessageIndex.id > after_id,
                MessageIndex.embedding.is_not(None),
                MessageIndex.embed_model == model,
            )
            .order_by(MessageIndex.id)
            .limit(limit)
        )
        return res.all()


async def get_by_ids(ids: Iterable[int]) -> list[MessageIndex]:
    ids = list(ids)
    if not ids:
        return []
    async with session_scope() as session:
        res = await session.execute(select(MessageIndex).where(MessageIndex.id.in_(ids)))
        return list(res.scalars().all())


async def lexical_candidates(
    tokens: Sequence[str],
    *,
    limit: int = 300,
    date_from: Optional[dt.datetime] = None,
    date_to: Optional[dt.datetime] = None,
) -> list[MessageIndex]:
    """پیام‌هایی که حداقل یکی از توکن‌ها (روی norm_text) توشونه؛ جدیدترها اول."""
    toks = [t for t in tokens if t]
    if not toks:
        return []
    cond = or_(*[MessageIndex.norm_text.like(f"%{_like_escape(t)}%", escape="\\") for t in toks])
    q = select(MessageIndex).where(cond)
    if date_from:
        q = q.where(MessageIndex.date >= date_from)
    if date_to:
        q = q.where(MessageIndex.date <= date_to)
    q = q.order_by(MessageIndex.date.desc()).limit(limit)
    async with session_scope() as session:
        return list((await session.execute(q)).scalars().all())


async def context_window(chat_id: int, date: dt.datetime, *, before: int = 4, after: int = 4) -> list[MessageIndex]:
    """پیام‌های اطرافِ یک زمان در همان چت (شاملِ خودِ پیام)، به ترتیبِ زمانی."""
    async with session_scope() as session:
        prev = (
            await session.execute(
                select(MessageIndex)
                .where(MessageIndex.chat_id == chat_id, MessageIndex.date <= date)
                .order_by(MessageIndex.date.desc(), MessageIndex.message_id.desc())
                .limit(before + 1)
            )
        ).scalars().all()
        nxt = (
            await session.execute(
                select(MessageIndex)
                .where(MessageIndex.chat_id == chat_id, MessageIndex.date > date)
                .order_by(MessageIndex.date.asc(), MessageIndex.message_id.asc())
                .limit(after)
            )
        ).scalars().all()
    return list(reversed(prev)) + list(nxt)


async def known_names(limit: int = 4000) -> list[tuple[int, Optional[str], Optional[int], Optional[str]]]:
    """(chat_id, chat_title, sender_id, sender_name) یکتا - برای تشخیصِ نامِ شخص در سوال."""
    async with session_scope() as session:
        res = await session.execute(
            select(
                MessageIndex.chat_id,
                MessageIndex.chat_title,
                MessageIndex.sender_id,
                MessageIndex.sender_name,
            )
            .distinct()
            .limit(limit)
        )
        return [tuple(r) for r in res.all()]


async def unembedded(limit: int = 64, model: Optional[str] = None) -> list[MessageIndex]:
    """پیام‌هایی که embeddingِ (مدلِ فعلی) ندارن: NULL، یا با مدلِ دیگه ساخته شدن."""
    cond = MessageIndex.embedding.is_(None)
    if model:
        cond = or_(cond, MessageIndex.embed_model != model)
    async with session_scope() as session:
        res = await session.execute(
            select(MessageIndex).where(cond).order_by(MessageIndex.id.desc()).limit(limit)
        )
        return list(res.scalars().all())


async def count_unembedded(model: Optional[str] = None) -> int:
    cond = MessageIndex.embedding.is_(None)
    if model:
        cond = or_(cond, MessageIndex.embed_model != model)
    async with session_scope() as session:
        return (await session.execute(select(func.count()).select_from(MessageIndex).where(cond))).scalar_one()


async def set_embeddings(items: Sequence[tuple[int, bytes, str]]) -> None:
    """items: (id, بردارِ bytes, نامِ مدل)"""
    if not items:
        return
    async with session_scope() as session:
        for row_id, blob, model in items:
            await session.execute(
                update(MessageIndex)
                .where(MessageIndex.id == row_id)
                .values(embedding=blob, embed_model=model)
            )


async def update_text(chat_id: int, message_id: int, text: str, norm_text: str) -> bool:
    """ویرایشِ پیام: متن عوض می‌شه و embedding باطل می‌شه (بعداً دوباره ساخته می‌شه)."""
    async with session_scope() as session:
        res = await session.execute(
            update(MessageIndex)
            .where(MessageIndex.chat_id == chat_id, MessageIndex.message_id == message_id)
            .values(text=text, norm_text=norm_text, embedding=None, embed_model=None)
        )
        return (res.rowcount or 0) > 0


async def delete_message(chat_id: Optional[int], message_id: int) -> int:
    """
    حذفِ یک پیام از ایندکس. تلگرام برای حذفِ پیام در پیوی/گروهِ‌ساده chat_id نمی‌ده
    (chat_id=None): شناسه‌ی پیام برای این چت‌ها در کلِ اکانت یکتاست، پس فقط روی
    چت‌های غیرِ‌کانال/سوپرگروه حذف می‌کنیم.
    """
    async with session_scope() as session:
        q = delete(MessageIndex).where(MessageIndex.message_id == message_id)
        if chat_id is not None:
            q = q.where(MessageIndex.chat_id == chat_id)
        else:
            q = q.where(MessageIndex.chat_kind.in_(("user", "group")), MessageIndex.chat_id > -1000000000000)
        res = await session.execute(q)
        return res.rowcount or 0


async def delete_chat(chat_id: int) -> int:
    async with session_scope() as session:
        res = await session.execute(delete(MessageIndex).where(MessageIndex.chat_id == chat_id))
        return res.rowcount or 0


async def delete_all() -> int:
    async with session_scope() as session:
        res = await session.execute(delete(MessageIndex))
        return res.rowcount or 0


async def trim_to_limit(max_rows: int) -> int:
    """اگه تعدادِ ردیف‌ها از سقف بیشتره، قدیمی‌ترین پیام‌ها (بر اساسِ تاریخِ پیام) حذف می‌شن."""
    total = await count_all()
    extra = total - max_rows
    if extra <= 0:
        return 0
    async with session_scope() as session:
        old_ids = (
            await session.execute(
                select(MessageIndex.id).order_by(MessageIndex.date.asc()).limit(extra)
            )
        ).scalars().all()
        if not old_ids:
            return 0
        old_ids = list(old_ids)
        for i in range(0, len(old_ids), 500):
            await session.execute(
                delete(MessageIndex).where(MessageIndex.id.in_(old_ids[i : i + 500]))
            )
        return len(old_ids)
