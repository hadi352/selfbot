"""
🧠 جستجوی معنایی در پیام‌های تلگرام.

  `.پرسش آخرین باری که درباره خرید گوشی صحبت کردم چی گفتیم؟`
     → (مسیریابیِ خودکار از handlers/ai.py) پیام‌های مرتبط رو بر اساسِ «معنا» پیدا می‌کنه،
       نامِ شخص + تاریخ رو می‌گه، در صورتِ نیاز گفتگو رو خلاصه می‌کنه، پیام‌های اصلی رو به‌عنوانِ
       منبع نشون می‌ده و لینکِ هر پیام رو می‌ده.
  `.پیام‌یاب <سوال>`  → همین جستجو، بدونِ مسیریابیِ خودکار (همیشه جستجوی پیام‌ها).
  `.ایندکس ...`       → روشن/خاموش، دامنه، پُرکردنِ تاریخچه، مستثنی‌کردنِ چت، پاک‌سازی، وضعیت.

حریمِ خصوصی (مهم): ایندکس *opt-in* و پیش‌فرض خاموشه. متنِ پیام‌ها توی دیتابیسِ خودت ذخیره
می‌شن و برای ساختنِ embedding به سرویسِ AI_EMBED_API_BASE فرستاده می‌شن. فقط چت‌های داخلِ
«دامنه» (پیش‌فرض: فقط پیوی) و غیرِ مستثنی ایندکس می‌شن؛ `.ایندکس پاک` همه‌چیز رو حذف می‌کنه.
"""
import asyncio
import datetime as dt
import logging
import time
from typing import Optional

from telethon import errors, events
from telethon.tl.types import Channel, Chat, User

from .. import ai, config, runtime, semantic_search as ss
from ..config import PREFIX
from ..runtime import client
from ..storage.semantic_store import SCOPES, exclude_chat, include_chat, is_excluded, semantic_state, set_scope
from ..storage.settings_toggles import set_toggle, toggles
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from .global_search import _md_escape, _message_link, _truncate

logger = logging.getLogger("selfbot.handlers.semantic")

_SCOPE_FA = {"private": "فقط پیوی", "groups": "پیوی + گروه‌ها", "all": "همه (با کانال‌ها)"}
_SCOPE_ALIASES = {
    "خصوصی": "private", "پیوی": "private", "private": "private", "pv": "private",
    "گروه": "groups", "گروه‌ها": "groups", "groups": "groups",
    "همه": "all", "all": "all",
}
_TG_LIMIT = 3800  # زیرِ سقفِ ۴۰۹۶ کاراکترِ تلگرام
# پیام‌های ادامه‌ی نتایج (respond) با این نویسه‌ی نامرئی شروع می‌شن تا ایندکسِ زنده، خروجیِ خودِ
# ربات رو به‌عنوانِ «پیامِ کاربر» ایندکس نکنه (حلقه‌ی بازخورد).
_BOT_MARK = "\u2063"

# ------------------------------------------------------- ایندکسِ زنده ---
_pending: list[dict] = []
_FLUSH_SIZE = 20
_flush_lock = asyncio.Lock()
_backfill_task: Optional[asyncio.Task] = None
_backfill_cancel = False


def _kind_of(chat) -> str:
    if isinstance(chat, User):
        return "user"
    if isinstance(chat, Channel):
        return "channel" if getattr(chat, "broadcast", False) else "group"
    if isinstance(chat, Chat):
        return "group"
    return "user"


def _in_scope(kind: str) -> bool:
    scope = semantic_state["scope"]
    if scope == "private":
        return kind == "user"
    if scope == "groups":
        return kind in ("user", "group")
    return True


def _name_of(entity) -> Optional[str]:
    if entity is None:
        return None
    title = getattr(entity, "title", None)
    if title:
        return title
    full = " ".join(filter(None, [getattr(entity, "first_name", None), getattr(entity, "last_name", None)]))
    return full or getattr(entity, "username", None)


async def _row_from_message(msg, chat, *, my_id: Optional[int] = None) -> Optional[dict]:
    """یک پیامِ تلتون → ردیفِ ایندکس (یا None اگه نباید ایندکس بشه)."""
    text = (getattr(msg, "raw_text", None) or "").strip()
    if not ss.should_index_text(text):
        return None
    if getattr(msg, "action", None) is not None:  # پیامِ سرویسی
        return None
    if text.startswith(_BOT_MARK):  # خروجیِ خودِ ربات
        return None
    out = bool(getattr(msg, "out", False))
    if out and text.startswith(PREFIX):  # دستورِ سلف‌بات، نه گفتگو
        return None
    kind = _kind_of(chat)
    if not _in_scope(kind):
        return None
    chat_id = getattr(msg, "chat_id", None)
    if chat_id is None or is_excluded(chat_id):
        return None
    if chat_id == runtime.SELF_ID:  # «پیام‌های ذخیره‌شده»: پُرِ خروجیِ رباته (نتایج، لیست‌ها، ...)
        return None

    sender = None
    try:
        sender = await msg.get_sender()
    except Exception:
        pass
    if getattr(sender, "bot", False):
        return None
    sender_id = getattr(msg, "sender_id", None)
    sender_name = _name_of(sender) if not out else None
    return ss.make_row(
        chat_id=chat_id,
        message_id=msg.id,
        chat_title=_name_of(chat),
        chat_username=getattr(chat, "username", None),
        chat_kind=kind,
        sender_id=sender_id,
        sender_name=sender_name,
        is_out=out,
        text=text,
        date=msg.date,
    )


async def _flush(force: bool = False) -> int:
    """ردیف‌های منتظر رو embed + ذخیره می‌کنه. خطا هیچ‌وقت نباید جریانِ ربات رو بشکنه."""
    global _pending
    async with _flush_lock:
        if not _pending or (len(_pending) < _FLUSH_SIZE and not force):
            return 0
        batch, _pending = _pending, []
        try:
            n = await ss.index_rows(batch)
            await ss.enforce_limit()
            return n
        except Exception:
            logger.exception("ذخیره‌ی پیام‌ها در ایندکس ناموفق بود")
            return 0


@client.on(events.NewMessage())
async def semantic_live_indexer(event):
    if not toggles.get("semantic_index_enabled", False):
        return
    try:
        chat = await event.get_chat()
        row = await _row_from_message(event.message, chat)
        if row is None:
            return
        _pending.append(row)
        if len(_pending) >= _FLUSH_SIZE:
            await _flush()
    except Exception:
        logger.exception("خطا در ایندکسِ زنده‌ی پیام")


@client.on(events.MessageEdited(incoming=True))
async def semantic_live_edit(event):
    """ویرایشِ پیامِ ورودی → متن به‌روز و embedding دوباره ساخته می‌شه (بعداً توسطِ worker)."""
    if not toggles.get("semantic_index_enabled", False):
        return
    try:
        text = (event.message.raw_text or "").strip()
        if not text or not ss.should_index_text(text):
            return
        from ..repositories import message_index_repo as repo

        if await repo.update_text(event.chat_id, event.message.id, text[:4000], ss.normalize_text(text)[:4000]):
            ss.cache.invalidate()
    except Exception:
        logger.exception("خطا در به‌روزرسانیِ پیامِ ویرایش‌شده در ایندکس")


@client.on(events.MessageDeleted())
async def semantic_live_delete(event):
    """پیامِ حذف‌شده از ایندکس هم حذف می‌شه (حریمِ خصوصی: حذف = فراموش)."""
    if not toggles.get("semantic_index_enabled", False):
        return
    try:
        from ..repositories import message_index_repo as repo

        removed = 0
        for mid in event.deleted_ids or []:
            removed += await repo.delete_message(getattr(event, "chat_id", None), mid)
        if removed:
            ss.cache.invalidate()
    except Exception:
        logger.exception("خطا در حذفِ پیام از ایندکس")


async def semantic_index_worker():
    """هر چند ثانیه: ذخیره‌ی ردیف‌های منتظر + تکمیلِ embeddingِ ردیف‌های بدونِ بردار."""
    while True:
        await asyncio.sleep(15)
        try:
            await _flush(force=True)
            if toggles.get("semantic_index_enabled", False) and ss.embeddings_enabled():
                await ss.complete_missing()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("خطا در workerِ ایندکسِ معنایی")


# --------------------------------------------------- پُرکردنِ تاریخچه ---
async def _backfill_chat(chat, limit: int, progress) -> int:
    """آخرین `limit` پیامِ یک چت رو ایندکس می‌کنه (پیام‌های موجود دوباره embed نمی‌شن)."""
    from ..repositories import message_index_repo as repo

    kind = _kind_of(chat)
    if not _in_scope(kind) or is_excluded(getattr(chat, "id", 0)):
        return 0
    added = 0
    buf: list = []

    async def _commit():
        nonlocal added, buf
        if not buf:
            return
        ids = [m.id for m in buf]
        chat_id = buf[0].chat_id
        have = await repo.existing_ids(chat_id, ids)
        rows = []
        for m in buf:
            if m.id in have:
                continue
            r = await _row_from_message(m, chat)
            if r:
                rows.append(r)
        buf = []
        if rows:
            await ss.index_rows(rows)
            added += len(rows)
            await progress(len(rows))

    async for m in client.iter_messages(chat, limit=limit):
        if _backfill_cancel:
            break
        buf.append(m)
        if len(buf) >= 100:
            await _commit()
            await asyncio.sleep(0.4)  # فشار نیاد روی تلگرام/سرویسِ embedding
    await _commit()
    return added


async def _run_backfill(event, scope_arg: str, per_chat: int):
    global _backfill_cancel
    _backfill_cancel = False
    started = time.monotonic()
    total = 0
    chats_done = 0
    last_edit = 0.0

    async def progress(n: int):
        nonlocal total, last_edit
        total += n
        now = time.monotonic()
        if now - last_edit > 6:
            last_edit = now
            try:
                await event.edit(f"⏳ در حال ایندکس... {total} پیام تا الان ({chats_done} چت)\n`{PREFIX}ایندکس توقف` برای لغو")
            except Exception:
                pass

    try:
        if scope_arg == "this":
            chat = await event.get_chat()
            total += await _backfill_chat(chat, per_chat, progress)
            chats_done = 1
        else:
            async for d in client.iter_dialogs():
                if _backfill_cancel:
                    break
                ent = d.entity
                if _kind_of(ent) == "user" and (getattr(ent, "bot", False) or getattr(ent, "is_self", False)):
                    continue
                try:
                    await _backfill_chat(ent, per_chat, progress)
                except errors.FloodWaitError as e:
                    logger.warning("FloodWait موقعِ ایندکس: %s ثانیه", e.seconds)
                    await asyncio.sleep(min(e.seconds, 120))
                except Exception:
                    logger.exception("ایندکسِ یک چت ناموفق بود")
                chats_done += 1
        removed = await ss.enforce_limit()
        secs = int(time.monotonic() - started)
        state = "⏹ متوقف شد" if _backfill_cancel else "✅ تمام شد"
        extra = f"\n🧹 {removed} پیامِ قدیمی (بالاتر از سقفِ {config.SEMANTIC_MAX_INDEX}) حذف شد." if removed else ""
        emb = "" if ss.embeddings_enabled() else "\n⚠️ embedding در دسترس نیست؛ فعلاً جستجوی کلمه‌ای کار می‌کنه (بعداً `.ایندکس بازسازی`)."
        await event.edit(f"{state}: {total} پیام ایندکس شد ({chats_done} چت، {secs} ثانیه).{extra}{emb}")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _record_error()
        logger.exception("ایندکسِ تاریخچه ناموفق بود")
        try:
            await event.edit(f"❌ خطا در ایندکس: {e}")
        except Exception:
            pass


# ------------------------------------------------------------ `.ایندکس` ---
def _status_text(total: int, embedded: int, unembedded: int, first, last, top) -> str:
    on = "🟢 روشن" if toggles.get("semantic_index_enabled", False) else "🔴 خاموش"
    auto = "روشن" if toggles.get("semantic_auto_route", True) else "خاموش"
    emb = (
        f"✅ `{ss.embed_tag()}`" if ss.embeddings_enabled()
        else "❌ غیرفعال (جستجوی کلمه‌ای + بسطِ AI)"
    )
    lines = [
        "🧠 **ایندکسِ جستجوی معنایی**",
        f"وضعیت: {on}   |   دامنه: {_SCOPE_FA[semantic_state['scope']]}",
        f"Embedding: {emb}",
        f"مسیریابیِ خودکارِ `.پرسش`: {auto}",
        f"📚 پیام‌های ایندکس‌شده: {total} (با بردار: {embedded}" + (f"، منتظرِ بردار: {unembedded}" if unembedded else "") + ")",
    ]
    if first and last:
        lines.append(f"🗓 بازه: {ss.format_date_fa(first, with_time=False)} تا {ss.format_date_fa(last, with_time=False)}")
    if top:
        lines.append("💬 پرپیام‌ترین‌ها: " + "، ".join(f"{_md_escape(t or str(c))} ({n})" for c, t, n in top[:5]))
    if semantic_state["excluded"]:
        lines.append(f"🚫 چت‌های مستثنی: {len(semantic_state['excluded'])}")
    return "\n".join(lines)


_HELP = (
    "\n\n**دستورها**\n"
    f"`{PREFIX}ایندکس روشن` / `خاموش` — شروع/توقفِ ایندکسِ پیام‌های جدید\n"
    f"`{PREFIX}ایندکس دامنه خصوصی|گروه‌ها|همه`\n"
    f"`{PREFIX}ایندکس شروع [تعدادِ پیام در هر چت=500] [این|همه]` — پُرکردنِ تاریخچه\n"
    f"`{PREFIX}ایندکس توقف` — لغوِ پُرکردن\n"
    f"`{PREFIX}ایندکس نادیده` — (در همین چت) این چت ایندکس نشه؛ دوباره = برگردوندن\n"
    f"`{PREFIX}ایندکس بازسازی` — ساختنِ embeddingِ پیام‌های بدونِ بردار/مدلِ قدیمی\n"
    f"`{PREFIX}ایندکس پاک تایید` — حذفِ کلِ ایندکس\n"
    f"`{PREFIX}ایندکس مسیر روشن|خاموش` — مسیریابیِ خودکارِ `.پرسش`\n\n"
    f"🔎 `{PREFIX}پرسش آخرین باری که درباره خرید گوشی صحبت کردم چی گفتیم؟`\n"
    f"🔎 `{PREFIX}پیام‌یاب <سوال>` — همیشه جستجوی پیام‌ها"
)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ایندکس", "index"])))
async def index_handler(event):
    global _backfill_task, _backfill_cancel
    from ..repositories import message_index_repo as repo

    args = (event.pattern_match.group(1) or "").strip().split()
    sub = args[0].lower() if args else ""

    if not sub:
        total = await repo.count_all()
        embedded = await repo.count_embedded(ss.embed_tag())
        first, last = await repo.date_range() if total else (None, None)
        top = await repo.top_chats() if total else []
        return await event.edit(_status_text(total, embedded, total - embedded, first, last, top) + _HELP)

    if sub in ("روشن", "on", "1"):
        await set_toggle("semantic_index_enabled", True)
        return await event.edit(
            "🟢 ایندکسِ پیام‌ها **روشن** شد.\n"
            f"از این به بعد پیام‌های {_SCOPE_FA[semantic_state['scope']]} ذخیره و برای جستجوی معنایی ایندکس می‌شن.\n"
            "⚠️ متنِ پیام‌ها برای ساختنِ embedding به سرویسِ AI فرستاده می‌شه.\n"
            f"برای پیام‌های قبلی: `{PREFIX}ایندکس شروع 500 همه`"
        )
    if sub in ("خاموش", "off", "0"):
        await set_toggle("semantic_index_enabled", False)
        await _flush(force=True)
        return await event.edit(
            f"🔴 ایندکسِ پیام‌های جدید **خاموش** شد. (آنچه تا الان ذخیره شده می‌مونه؛ برای حذف: `{PREFIX}ایندکس پاک تایید`)"
        )

    if sub in ("مسیر", "route"):
        val = args[1].lower() if len(args) > 1 else ""
        if val in ("روشن", "on", "1"):
            await set_toggle("semantic_auto_route", True)
            return await event.edit("🧠 مسیریابیِ خودکارِ `.پرسش` روشن شد.")
        if val in ("خاموش", "off", "0"):
            await set_toggle("semantic_auto_route", False)
            return await event.edit(f"🧠 مسیریابیِ خودکار خاموش شد؛ فقط با `{PREFIX}پیام‌یاب` جستجو می‌شه.")
        return await event.edit(f"مثال: `{PREFIX}ایندکس مسیر روشن`")

    if sub in ("دامنه", "scope"):
        val = _SCOPE_ALIASES.get(args[1].lower()) if len(args) > 1 else None
        if not val:
            return await event.edit(
                f"دامنه‌ی فعلی: **{_SCOPE_FA[semantic_state['scope']]}**\n"
                f"`{PREFIX}ایندکس دامنه خصوصی|گروه‌ها|همه`"
            )
        await set_scope(val)
        return await event.edit(f"✅ دامنه روی **{_SCOPE_FA[val]}** تنظیم شد.")

    if sub in ("شروع", "start", "backfill"):
        if _backfill_task and not _backfill_task.done():
            return await event.edit(f"⏳ یک ایندکسِ دیگه در حالِ اجراست. `{PREFIX}ایندکس توقف` برای لغو.")
        per_chat, where = 500, "this"
        for a in args[1:]:
            if a.isdigit():
                per_chat = max(10, min(int(a), 20000))
            elif a in ("همه", "all"):
                where = "all"
            elif a in ("این", "this"):
                where = "this"
        if not toggles.get("semantic_index_enabled", False):
            await set_toggle("semantic_index_enabled", True)
        await event.edit(f"⏳ شروعِ ایندکس ({'همه‌ی چت‌های دامنه' if where == 'all' else 'این چت'}، تا {per_chat} پیام در هر چت)...")
        _backfill_task = asyncio.create_task(_run_backfill(event, where, per_chat))
        return

    if sub in ("توقف", "stop"):
        if _backfill_task and not _backfill_task.done():
            _backfill_cancel = True
            return await event.edit("⏹ درخواستِ توقف ثبت شد...")
        return await event.edit("ایندکسِ در حالِ اجرایی نیست.")

    if sub in ("نادیده", "ignore", "exclude"):
        cid = event.chat_id
        if is_excluded(cid):
            await include_chat(cid)
            return await event.edit("✅ این چت دوباره قابلِ ایندکس شد.")
        await exclude_chat(cid)
        removed = await repo.delete_chat(cid)
        ss.cache.invalidate()
        return await event.edit(f"🚫 این چت از ایندکس مستثنی شد ({removed} پیامِ قبلی‌اش هم حذف شد).")

    if sub in ("بازسازی", "rebuild"):
        await event.edit("⏳ در حالِ ساختنِ embedding...")
        if not ss.embeddings_enabled():
            return await event.edit("❌ embedding در دسترس نیست: AI_API_KEY (یا AI_EMBED_API_KEY) و numpy لازمه.")
        done = 0
        for _ in range(200):  # سقفِ ایمنی: ~۱۲٬۸۰۰ پیام در هر بار
            n = await ss.complete_missing(64)
            if not n:
                break
            done += n
            if done % 640 == 0:
                try:
                    await event.edit(f"⏳ {done} پیام embedding گرفت...")
                except Exception:
                    pass
            await asyncio.sleep(0.3)
        left = await repo.count_unembedded(ss.embed_tag())
        return await event.edit(f"✅ {done} پیام embedding گرفت." + (f" ({left} مورد مونده؛ دوباره بزن)" if left else ""))

    if sub in ("پاک", "clear", "wipe"):
        if "تایید" not in args and "confirm" not in args:
            total = await repo.count_all()
            return await event.edit(f"⚠️ این کار {total} پیامِ ایندکس‌شده رو برای همیشه حذف می‌کنه.\nتأیید: `{PREFIX}ایندکس پاک تایید`")
        n = await repo.delete_all()
        _pending.clear()
        ss.cache.invalidate()
        return await event.edit(f"🗑 ایندکس پاک شد ({n} پیام).")

    return await event.edit("زیردستورِ نامعتبر." + _HELP)


# ------------------------------------------------- پرسش و نمایشِ نتایج ---
def _paginate(blocks: list[str], limit: int = _TG_LIMIT) -> list[str]:
    pages, cur, cur_len = [], [], 0
    for b in blocks:
        if cur and cur_len + len(b) + 2 > limit:
            pages.append("\n\n".join(cur))
            cur, cur_len = [], 0
        cur.append(b)
        cur_len += len(b) + 2
    if cur:
        pages.append("\n\n".join(cur))
    return pages or [""]


def _source_block(i: int, w: ss.Window, now) -> str:
    """بلوکِ منبعِ i: نامِ شخص/چت، تاریخ، پیام‌های اصلیِ پیداشده + لینکِ دقیقِ پیام."""
    first = w.messages[0] if w.messages else w.best.row
    when = f"{ss.format_date_fa(w.best.row.date)} ({ss.age_fa(w.best.row.date, now)})"
    kind_icon = {"user": "👤", "group": "👥", "channel": "📢"}.get(w.kind, "💬")
    lines = [f"**{i}.** {kind_icon} {_md_escape(w.title)} — 📅 {when}"]
    shown = sorted(w.hits, key=lambda h: (h.row.date, h.row.message_id))[:3]
    for h in shown:
        r = h.row
        who = _md_escape(ss.display_sender(r))
        quote = _md_escape(_truncate((r.text or "").replace("\n", " "), 160))
        link = _message_link(r.chat_id, r.message_id, r.chat_username)
        lines.append(f"   ▫️ {who}: «{quote}»\n      🔗 [باز کردنِ پیام]({link})")
    extra = len(w.messages) - len(shown)
    if extra > 0:
        lines.append(f"   _… و {extra} پیامِ دیگر از همین گفتگو_")
    return "\n".join(lines)


async def _deliver(event, pages: list[str], *, ai_tag: bool) -> None:
    """
    حریمِ خصوصی: نتیجه شاملِ پیام‌های *چت‌های دیگه‌ست*؛ اگه دستور توی چتِ یه نفر زده شده
    باشه، نمایشِ درجا یعنی اون نفر محتوای چت‌های دیگه‌ی تو رو می‌بینه. پس به‌طورِ پیش‌فرض
    نتیجه توی «پیام‌های ذخیره‌شده» فرستاده می‌شه (مگه خودِ دستور اونجا زده شده باشه، یا
    SEMANTIC_REPLY_IN_PLACE=true).
    """
    in_place = event.chat_id == runtime.SELF_ID or config.SEMANTIC_REPLY_IN_PLACE
    tag = f"\n\n||{config.AI_TAG_TEXT}||" if (ai_tag and config.AI_TAG_ENABLED) else ""
    if in_place:
        pages = pages[:-1] + [pages[-1] + tag]
        await event.edit(pages[0], link_preview=False)
        for p in pages[1:]:
            await asyncio.sleep(0.35)
            await event.respond(_BOT_MARK + p, link_preview=False)
        return
    for p in pages:
        await client.send_message("me", _BOT_MARK + p + (tag if p is pages[-1] else ""), link_preview=False)
        await asyncio.sleep(0.35)
    await event.edit("🔒 نتیجه به «پیام‌های ذخیره‌شده»ی خودت فرستاده شد (چون شاملِ پیام‌های چت‌های دیگه‌ست).")


async def answer_recall(event, question: str) -> None:
    """جستجوی معنایی + پاسخِ AI + منابع (نام، تاریخ، پیام‌های اصلی، لینک)."""
    await event.edit("🔎 در حالِ جستجو در پیام‌های قبلی...")
    try:
        res = await ss.search(question)
    except Exception as e:
        _record_error()
        logger.exception("جستجوی معنایی ناموفق بود")
        return await event.edit(f"❌ خطا در جستجوی پیام‌ها: {e}")

    if res.total_indexed == 0:
        return await event.edit(
            "📭 هنوز پیامی ایندکس نشده.\n"
            f"`{PREFIX}ایندکس روشن` و بعد `{PREFIX}ایندکس شروع 500 همه` رو بزن تا بتونم توی گفتگوهات بگردم."
        )
    if not res.windows:
        mode = "معنایی" if res.used_semantic else "کلمه‌ای"
        return await event.edit(
            f"🔍 توی {res.total_indexed} پیامِ ایندکس‌شده چیزِ مرتبطی پیدا نشد (جستجوی {mode}).\n"
            "عبارتِ دیگه‌ای امتحان کن، یا اگه گفتگو قدیمیه، تاریخچه رو با `.ایندکس شروع` اضافه کن."
        )

    now = dt.datetime.now(dt.timezone.utc)
    header = [f"🧠 **{_md_escape(_truncate(question, 120))}**"]
    notes = []
    if res.people:
        notes.append("👤 " + "، ".join(_md_escape(p) for p in res.people))
    if res.time_hint:
        notes.append(f"🕐 {res.time_hint.label}")
    elif res.relaxed_time:
        notes.append("🕐 در بازه‌ی زمانیِ ذکرشده چیزی نبود؛ کلِ تاریخچه جستجو شد")
    if not res.used_semantic:
        notes.append("🔤 جستجوی کلمه‌ای (embedding در دسترس نیست)")
    if notes:
        header.append(" · ".join(notes))

    # --- پاسخِ AI (اختیاری؛ اگه AI خاموش/خطا باشه، فقط منابع نشون داده می‌شه)
    answer, ai_note = "", ""
    try:
        answer = await ai.ask_ai(ss.build_prompt(question, res), max_tokens=max(config.AI_MAX_TOKENS, 500))
    except ai.AIDisabledError:
        ai_note = "ℹ️ AI_API_KEY تنظیم نیست؛ فقط پیام‌های پیداشده نمایش داده می‌شن."
    except ai.AIRequestError as e:
        _record_error()
        ai_note = f"⚠️ خلاصه‌سازیِ AI ناموفق بود ({_md_escape(str(e))}); پیام‌های پیداشده:"

    blocks = ["\n".join(header)]
    if answer:
        blocks.append(f"🤖 {_md_escape(answer)}")
    if ai_note:
        blocks.append(ai_note)
    blocks.append("📚 **منابع**")
    blocks += [_source_block(i, w, now) for i, w in enumerate(res.windows, 1)]
    await _deliver(event, _paginate(blocks), ai_tag=bool(answer))


async def should_route(question: str) -> bool:
    """آیا `.پرسش` باید این سوال رو به جستجوی پیام‌ها بده؟"""
    return bool(question) and toggles.get("semantic_auto_route", True) and ss.looks_like_recall(question)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پیام‌یاب", "پیام_یاب", "پیامیاب", "recall"])))
async def recall_handler(event):
    question = (event.pattern_match.group(1) or "").strip()
    if not question:
        return await event.edit(
            f"مثال: `{PREFIX}پیام‌یاب آخرین باری که درباره خرید گوشی صحبت کردم چی گفتیم؟`\n"
            f"وضعیتِ ایندکس: `{PREFIX}ایندکس`"
        )
    await answer_recall(event, question)
