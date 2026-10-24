"""📦 کپی کانال: `.کپی‌کانال` — فورواردِ همه‌ی پست‌های یک کانال به کانالِ دیگه.

مثال‌ها:
  .کپی‌کانال شروع @مبدا @مقصد            (از اولین پست؛ بدونِ برچسبِ Forwarded from)
  .کپی‌کانال شروع @مبدا @مقصد از 1200    (از پیامِ شماره‌ی 1200 به بعد)
  .کپی‌کانال شروع @مبدا @مقصد از 1403/05/01   (از تاریخِ شمسی به بعد — میلادی هم می‌شه)
  .کپی‌کانال شروع @مبدا @مقصد از امروز    (امروز/دیروز/پریروز + ساعتِ اختیاری)
  .کپی‌کانال شروع @مبدا @مقصد با‌نام      (با نامِ کانالِ مبدأ)
  .کپی‌کانال وضعیت / توقف / ادامه / لیست / حذف 3

رعایتِ محدودیت‌های تلگرام:
  • فوروارد دسته‌ای (پیش‌فرض ۲۰ پیام در هر درخواست؛ سقفِ تلگرام ۱۰۰) و آلبوم‌ها سالم می‌مونن
  • مکثِ ثابت بینِ دسته‌ها + صبر دقیق روی FloodWait/SlowMode
  • سقفِ روزانه فقط اگه CHANNEL_COPY_DAILY_LIMIT رو بزرگ‌تر از ۰ بذاری فعاله (پیش‌فرض: بدونِ سقف)
  • پیشرفت توی دیتابیس ذخیره می‌شه؛ بعد از توقف/ری‌استارت با «ادامه» دنبال می‌شه
  • کانال‌های با «محتوای محافظت‌شده» (noforwards) کپی نمی‌شن — این محدودیت دور زده نمی‌شه
"""
import asyncio
import datetime as dt
import logging
import re
import time

from telethon import events, utils as tl_utils
from telethon.tl.types import Channel, Chat, PeerChannel

from .. import config
from ..channel_copy_core import (
    FOLDER_MAX,
    UID_OFFSET,
    check_window,
    classify_error,
    extract_protected_links,
    find_start_id,
    format_from_date,
    format_status,
    iter_batches,
    parse_chat_ref,
    parse_start_any,
    ref_label,
    split_ref,
    start_variants,
    to_ascii_digits,
)
from ..repositories import channel_copy_repo as repo
from ..runtime import client
from ..utils import pat

logger = logging.getLogger(__name__)

_TASKS: dict[int, asyncio.Task] = {}
_STOP: dict[int, asyncio.Event] = {}
_LIVE: dict[int, dict] = {}
# کارهایی که در حالتِ «از این به بعد» منتظرن و پیامِ تازه‌ای نداشتن (برایِ پیامِ اعلانِ یک‌بارِ)
_IDLE_WATCH: dict[int, bool] = {}

_MAX_ATTEMPTS = 5
_MAX_BAD_BATCHES_IN_ROW = 5
_PER_MESSAGE_FALLBACK_DELAY = 3.0

USAGE = (
    "📦 **کپی کانال**\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مبدا @مقصد` — از اولین پست\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مقصد` + **ریپلای روی پستی از کانالِ مبدأ** — بدونِ آدرسِ مبدأ\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مبدا @مقصد از 1200` — از پیامِ 1200 به بعد\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مبدا @مقصد از 1403/05/01` — از تاریخِ شمسی به بعد\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مبدا @مقصد از 2024-08-22 ساعت 10:30` — تاریخِ میلادی + ساعت\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مبدا @مقصد از امروز` — امروز / دیروز / پریروز\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مبدا @مقصد از 1403/05/01 ازاین‌بعد` — از این تاریخ به بعد + هر پستِ تازه هم خودکار 👀\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مبدا1,@مبدا2,@مبدا3 @مقصد` — چند کانال با هم\n"
    f"`{config.PREFIX}کپی‌کانال شروع پوشه:3 @مقصد` — همه‌ی کانال‌های پوشه‌ی شماره‌ی ۳\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مبدا @مقصد با‌نام` — با برچسبِ Forwarded from\n\n"
    "🔒 **کانالِ خصوصی (بدونِ یوزرنیم):**\n"
    f"`{config.PREFIX}کپی‌کانال پیدا اخبار` — جستجو بینِ همه‌ی چت‌هات (کانالِ خصوصی هم میاد)\n"
    f"`{config.PREFIX}کپی‌کانال ذخیره اخبار @ch` — اسمِ دلخواه برای یک کانال\n"
    f"`{config.PREFIX}کپی‌کانال شروع` + **ریپلای** روی پیامِ همون کانال → مبدأ همون کانال می‌شه\n"
    f"`{config.PREFIX}کپی‌کانال شروع @مقصد` + ریپلای → ‌آدرسِ داده‌شده مقصده و مبدأ از پستِ ریپلای‌شده\n"
    f"`{config.PREFIX}کپی‌کانال پوشه‌ها` — لیستِ پوشه‌ها و شماره‌شون\n\n"
    f"`{config.PREFIX}کپی‌کانال وضعیت [شماره]` | `توقف [شماره]` | `ادامه [شماره]` | `لیست` | `حذف <شماره>`\n"
    "• «ادامه» روی کارِ تمام‌شده = فقط پست‌های تازه‌ی بعد از آخرین کپی‌شده (بدونِ تکرار).\n\n"
    "• مقصد باید کانالی باشه که توش ادمین (با دسترسیِ انتشار) هستی.\n"
    "• کانال‌های با «محتوای محافظت‌شده» کپی نمی‌شن."
)


class _Fatal(Exception):
    pass


class _Stopped(Exception):
    pass


def _is_flood(exc: BaseException) -> bool:
    """خطای «هر چند ثانیه صبر کن»ِ تلگرام (بر اساسِ نامِ کلاس، مستقل از نسخه‌ی Telethon)."""
    return any(
        cls.__name__ in ("FloodWaitError", "SlowModeWaitError", "FloodPremiumWaitError")
        for cls in type(exc).__mro__
    )


# --------------------------------------------------------------- utils ---
async def _sleep(stop: asyncio.Event, seconds: float) -> bool:
    """مکثِ قابلِ قطع. True یعنی «توقف» درخواست شده."""
    if stop.is_set():
        return True
    try:
        await asyncio.wait_for(stop.wait(), timeout=max(seconds, 0))
        return True
    except asyncio.TimeoutError:
        return False


async def _notify(text: str) -> None:
    """اعلان توی Saved Messages (نه توی کانالِ مقصد/مبدأ تا پست‌ها آلوده نشن)."""
    try:
        await client.send_message("me", text)
    except Exception:
        logger.warning("ارسالِ اعلانِ کپی‌کانال ناموفق بود", exc_info=True)


async def _resolve(kind_value: tuple[str, object] | None, stored_id: int | None, stored_ref: str = ""):
    """entity رو پیدا می‌کنه. بعد از ری‌استارت کَشِ entity خالیه → یک‌بار get_dialogs."""
    candidates = []
    if kind_value is not None:
        kind, val = kind_value
        candidates.append(PeerChannel(val) if kind == "id" and val > 0 else val)
    if stored_id is not None:
        candidates.append(stored_id)
    if stored_ref and not stored_ref.lstrip("-").isdigit():
        candidates.append(stored_ref)

    # تلاش اول: مستقیم
    for c in candidates:
        try:
            return await asyncio.wait_for(client.get_entity(c), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("get_entity(%r) timeout شد", c)
            continue
        except (ValueError, TypeError):
            continue
        except Exception as e:
            logger.debug("get_entity(%r) failed: %s", c, e)
            continue
    
    # تلاش دوم: بعد از get_dialogs
    await _warm_dialogs()

    for c in candidates:
        try:
            return await asyncio.wait_for(client.get_entity(c), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("get_entity(%r) timeout شد (دومین تلاش)", c)
            continue
        except (ValueError, TypeError):
            continue
        except Exception as e:
            logger.debug("get_entity(%r) failed (دومین تلاش): %s", c, e)
            continue
    
    return None


async def _warm_dialogs() -> None:
    """کَشِ entity/پوشه‌ها رو پر می‌کنه (بعد از ری‌استارت لازمه). خطا مهم نیست."""
    for kw in ({}, {"folder": 1}, {"folder": 0}):
        try:
            await asyncio.wait_for(client.get_dialogs(**kw), timeout=20)
            return
        except asyncio.TimeoutError:
            logger.warning("get_dialogs(%s) timeout شد", kw)
        except Exception:
            logger.debug("get_dialogs(%s) ناموفق بود", kw, exc_info=True)


def _norm_search(s: str) -> str:
    """نرمال‌سازی برای جستجوی فارسی: ی/ك عربی، ارقام، حذفِ فاصله‌ی مجازی و نیم‌فاصله."""
    s = to_ascii_digits(s or "").strip().lower()
    s = s.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه").replace("ة", "ه")
    s = s.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    return " ".join(s.split())


def _is_channel_like(ent) -> bool:
    return isinstance(ent, (Channel, Chat))


async def _folder_names() -> dict[int, str]:
    """{شناسه‌ی پوشه: اسمِ پوشه} — از GetDialogFilters؛ ممکنه خالی برگرده."""
    out: dict[int, str] = {}
    try:
        from telethon.tl.functions.messages import GetDialogFiltersRequest

        res = await asyncio.wait_for(client(GetDialogFiltersRequest()), timeout=20)
        for f in getattr(res, "filters", []):
            fid, title = getattr(f, "id", None), getattr(f, "title", None)
            if not isinstance(fid, int):
                fid = getattr(fid, "id", None)
            if isinstance(fid, int):
                out[fid] = str(getattr(title, "text", None) or title or "")
    except Exception:
        logger.debug("اسمِ پوشه‌ها خونده نشد", exc_info=True)
    return out


async def _search_targets(query: str = "", folder: int | None = None, limit: int = 40):
    """
    جستجو بین کانال/گروه‌هایی که عضوشون هستی (کانالِ خصوصی هم هست).
    query: بخشی از اسم/یوزرنیم (فارسی نرمال‌سازی می‌شه) • folder: فقط داخلِ یک پوشه.
    خروجی: [(entity, شماره‌ی کاملِ چت, عنوان), ...]
    """
    await _warm_dialogs()
    q = _norm_search(query)
    out: list[tuple[object, int, str]] = []
    seen: set[int] = set()
    try:
        kwargs = {"limit": None}
        if folder is not None:
            kwargs["folder"] = folder
        dialogs = await asyncio.wait_for(client.get_dialogs(**kwargs), timeout=180)
    except Exception:
        logger.warning("گرفتنِ لیستِ چت‌ها ناموفق بود", exc_info=True)
        return out
    for d in dialogs:
        ent = getattr(d, "entity", None)
        if not _is_channel_like(ent):
            continue
        pid = tl_utils.get_peer_id(ent)
        if pid in seen:
            continue
        title = _title(ent)
        if q and q not in _norm_search(f"{title} {getattr(ent, 'username', '') or ''} {pid}"):
            continue
        seen.add(pid)
        out.append((ent, pid, title))
        if len(out) >= limit:
            break
    return out


async def _publishable(_dst_id, ent) -> bool:
    """آیا توی این کانال/گروه می‌تونی (از سمتِ ما) پست منتشر کنی؟"""
    if getattr(ent, "noforwards", False) or getattr(ent, "join_request", False):
        return False
    if not isinstance(ent, Channel):
        return True  # گروه: چکِ دقیق توی مرحله‌ی قبل از ساختِ کار انجام می‌شه
    try:
        perms = await asyncio.wait_for(client.get_permissions(ent), timeout=15)
    except Exception:
        return False
    if perms is None:
        return True  # مالکِ کانال (perms برنمی‌گرده) — موقعِ فوروارد واقعی معلوم می‌شه
    if ent.broadcast:
        return bool(perms.is_creator or getattr(perms, "post_messages", False))
    return bool(perms.is_creator or getattr(perms, "is_admin", False) or getattr(perms, "send_messages", True))


async def _targets_for_scope(spec: str, dst_id: int, limit: int = 200):
    """
    یک «دامنه» رو به کانال‌ها تبدیل می‌کنه:
      • "folder:<N>"     → همه‌ی کانال/گروه‌های پوشه‌ی شماره‌ی N (اسم هم قابلِ قبوله)
      • "id:<chat_id>"   → همون یک کانال/گروه
      • "@username"      → همون یک کانال
    خروجی: [(entity, شماره‌ی کامل, عنوان), ...] بدونِ خودِ مقصد و بدونِ محتوای محافظت‌شده،
    و فقط اونایی که اجازه‌ی انتشار داریم.
    """
    spec = (spec or "").strip()
    if spec.startswith("folder:"):
        arg = spec.split(":", 1)[1].strip()
        fid: int | None = None
        if re.fullmatch(r"\d+", arg):
            fid = int(arg)
        else:
            names = await _folder_names()
            want = _norm_search(arg)
            exact = [k for k, v in names.items() if _norm_search(v) == want]
            near = [k for k, v in names.items() if want and want in _norm_search(v)]
            if exact:
                fid = exact[0]
            elif len(near) == 1:
                fid = near[0]
            elif near:
                lis = "، ".join(f"{names[k]} ({k})" for k in near)
                raise ValueError(f"چند پوشه به «{arg}» می‌خورن: {lis} — با شماره‌اش بگو.")
            else:
                raise ValueError(f"پوشه‌ای به اسمِ «{arg}» پیدا نشد (`.کپی‌کانال پوشه‌ها`).")
        found = await _search_targets("", folder=fid, limit=limit)
    else:
        kind_val = parse_chat_ref(spec)
        ent = await _resolve(kind_val, None, spec)
        if ent is None:
            raise ValueError(f"«{spec}» پیدا نشد (عضو هستی؟).")
        found = [(ent, tl_utils.get_peer_id(ent), _title(ent))]

    out = []
    for ent, pid, title in found:
        if pid == dst_id or not _is_channel_like(ent):
            continue
        if not await _publishable(dst_id, ent):
            continue
        out.append((ent, pid, title))
    if not out:
        raise ValueError("توی این دامنه کانال/گروهی پیدا نشد که بشه توش پست منتشر کرد.")
    return out


async def _find_by_protected_link(hash_id: int):
    """کانالِ خصوصی از «t.me/c/<شناسه>» → entity (وقتی آیدی‌های کاری توی لیستِ چت‌ها باشن)."""
    if hash_id <= 0:
        return None
    for kind, ref in (("id", hash_id), ("id", int(f"-100{hash_id}")), ("id", int(f"-{hash_id}"))):
        ent = await _resolve((kind, ref), None, "")
        if ent is not None:
            return ent
    return None


async def _find_channel_by_inner_id(sh_short: int, sh_full: int):
    """
    پیدا کردنِ کانالِ خصوصی از «شناسه‌ی داخلی» (t.me/c/<id>) با اسکنِ لیستِ چت‌ها
    و مقایسه‌ی شناسه‌ی داخلی + peer_id (چون لینک‌هایِ داخلِ کانال این شناسه‌ها رو دارن).
    """
    if sh_short <= 0:
        return None
    await _warm_dialogs()
    try:
        dialogs = await asyncio.wait_for(client.get_dialogs(limit=None), timeout=180)
    except Exception:
        logger.warning("اسکنِ لیستِ چت‌ها ناموفق بود", exc_info=True)
        return None
    for d in dialogs:
        ent = getattr(d, "entity", None)
        if not _is_channel_like(ent):
            continue
        inner = getattr(getattr(ent, "id", None), "channel_id", None)
        if inner is None:
            inner = getattr(ent, "id", None)
        pid = tl_utils.get_peer_id(ent)
        if inner == sh_short or pid == sh_full:
            return ent
    return None


async def _check_invite(hash_str: str) -> str | None:
    """
    لینکِ دعوتِ خصوصی → اسمِ کانال (یا None).
    هیچ‌وقت عضو نمی‌شه (ImportChatInvite توی این قابلیت صدا زده نمی‌شه).
    """
    try:
        from telethon.tl.functions.messages import CheckChatInviteRequest

        res = await asyncio.wait_for(client(CheckChatInviteRequest(hash_str)), timeout=20)
    except Exception as e:
        logger.info("بررسی لینکِ دعوت ناموفق بود: %s", e)
        return None
    chat = getattr(res, "chat", None)
    if chat is not None:
        return _title(chat)
    inviter = getattr(res, "about", None) or ""
    if getattr(res, "title", None):
        return str(res.title)
    return str(inviter) or "کانالِ خصوصی"


def _title(entity) -> str:
    return getattr(entity, "title", None) or getattr(entity, "username", None) or str(entity.id)


async def _validate_pair(src, dst) -> str | None:
    """None = مشکلی نیست؛ وگرنه متنِ خطا."""
    for e, label in ((src, "مبدأ"), (dst, "مقصد")):
        if not isinstance(e, (Channel, Chat)):
            return f"{label} باید کانال یا گروه باشه (نه کاربر/بات)."
    if tl_utils.get_peer_id(src) == tl_utils.get_peer_id(dst):
        return "مبدأ و مقصد یکی‌ان."
    if getattr(src, "noforwards", False):
        return (
            "این کانال «محتوای محافظت‌شده» داره (مالکش فوروارد/ذخیره رو بسته)؛ "
            "تلگرام اجازه‌ی کپی نمی‌ده و این محدودیت دور زده نمی‌شه."
        )
    if isinstance(dst, Channel):
        try:
            perms = await asyncio.wait_for(client.get_permissions(dst), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("get_permissions timeout شد")
            return "درخواست دسترسی‌ها timeout شد. دوباره تلاش کن."
        except Exception as e:
            logger.warning("get_permissions failed: %s", e)
            return f"نتونستم دسترسی‌هات رو توی مقصد بررسی کنم: {e}"
        
        if perms is None:
            # اگر مالک کانال هستی ولی perms برنمی‌گرده، احتمالاً مشکل cache است
            # بذار بدون چک ادامه بده و اگر واقعاً مشکل باشه موقع فوروارد معلوم می‌شه
            logger.warning("perms is None for channel %s - skipping permission check", dst.id)
        elif dst.broadcast:
            if not (perms.is_creator or getattr(perms, "post_messages", False)):
                return "توی کانالِ مقصد دسترسیِ انتشارِ پست نداری (باید سازنده یا ادمین باشی)."
        elif not (perms.is_creator or perms.is_admin or getattr(perms, "send_messages", True)):
            return "توی گروهِ مقصد اجازه‌ی ارسال نداری."
    return None


# ------------------------------------------------------------- forward ---
async def _fetch_dates(src, ids: list[int]) -> dict[int, dt.datetime]:
    """
    شناسه‌ها → تاریخشون (فقطِ پیام‌های موجود)؛ برای پیدا کردنِ مرزِ تاریخ.
    هر درخواست حداکثرِ ۱۰۰ شناسه (سقفِ channels.getMessages) + صبرِ احتمالی روی FloodWait.
    """
    out: dict[int, dt.datetime] = {}
    ids = [i for i in dict.fromkeys(int(x) for x in ids) if i > 0]
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        res = None
        for attempt in range(3):
            try:
                res = await asyncio.wait_for(client.get_messages(src, ids=chunk), timeout=45)
                break
            except asyncio.TimeoutError:
                logger.warning("get_messages(ids) timeout شد (تلاش %s)", attempt + 1)
                continue
            except Exception as e:
                kind, val = classify_error(e)
                if kind == "wait":
                    logger.info("کپی‌کانال: تلگرام %s ثانیه صبر خواست (خوندنِ تاریخ‌ها)", val)
                    await asyncio.sleep(val + 1)
                    continue
                if kind == "fatal":
                    raise
                logger.warning("get_messages(ids) خطا: %r", e)
                await asyncio.sleep(2)
        if res is None:
            continue
        for m in res:
            if m is None:
                continue
            mid, d = getattr(m, "id", None), getattr(m, "date", None)
            if mid and d is not None:
                out[int(mid)] = d
        await asyncio.sleep(0.3)  # ملایم با تلگرام؛ کلِ جستجو چند ثانیه بیشتر طول نمی‌کشه
    return out


async def _start_id_by_date(src, from_date: dt.datetime, *, start_after: int = 0, cap_id: int = 0) -> int | None:
    """
    اولین شناسه‌ی پیامی که هم از تاریخِ خواسته‌شده به بعده و هم از start_after جلوتره
    (یا None). cap_id: آخرین شناسه‌ی مبدأ؛ ۰ = خودت پیدا کن.
    """
    # از وقتِ کاربر (بدونِ tz) به UTC — پیام‌های تلگرام UTC هستن
    target = (from_date - dt.timedelta(hours=config.TIMEZONE_OFFSET)).replace(tzinfo=dt.timezone.utc)
    if not cap_id:
        try:
            latest = list(await asyncio.wait_for(client.get_messages(src, limit=1), timeout=30))
        except Exception:
            logger.warning("گرفتنِ آخرین پیامِ مبدأ ناموفق بود", exc_info=True)
            latest = []
        cap_id = int(latest[0].id) if latest else 0
    return await find_start_id(lambda ids: _fetch_dates(src, ids), max(1, int(start_after) + 1), int(cap_id), target)


async def _do_forward(dst, src, ids: list[int], drop_author: bool):
    kwargs = {"from_peer": src, "silent": True}
    if drop_author:
        kwargs["drop_author"] = True
    try:
        return await client.forward_messages(dst, ids, **kwargs)
    except TypeError as e:
        if "drop_author" in str(e):
            raise _Fatal("نسخه‌ی Telethon قدیمیه (drop_author پشتیبانی نمی‌شه). با `pip install -U telethon` به‌روزش کن.")
        raise


def _count(res, n: int) -> tuple[int, int]:
    if res is None:
        return 0, n
    if isinstance(res, (list, tuple)):
        ok = sum(1 for m in res if m is not None)
    else:
        ok = 1
    return min(ok, n), max(n - ok, 0)


async def _forward_safe(job_id: int, dst, src, ids: list[int], drop_author: bool, stop: asyncio.Event) -> tuple[int, int]:
    """(کپی‌شده, ردشده). _Fatal/_Stopped می‌اندازه."""
    live = _LIVE.setdefault(job_id, {})
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            res = await _do_forward(dst, src, ids, drop_author)
            return _count(res, len(ids))
        except (_Fatal, _Stopped):
            raise
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if _is_flood(e):
                # «انتظار»ها نباید با سقفِ تلاش تموم بشن — هر چقدر تلگرام خواست صبر می‌کنیم
                try:
                    secs = max(int(getattr(e, "seconds", 30) or 30), 1)
                except (TypeError, ValueError):
                    secs = 30
                live["state"] = f"انتظارِ تلگرام ({secs} ثانیه)"
                logger.info("کپی‌کانال #%s: wait %ss (%s)", job_id, secs, e.__class__.__name__)
                if await _sleep(stop, secs + 1):
                    raise _Stopped()
                continue
            kind, val = classify_error(e)
            if kind == "wait":
                live["state"] = f"انتظارِ تلگرام ({val} ثانیه)"
                logger.info("کپی‌کانال #%s: wait %ss (%s)", job_id, val, e.__class__.__name__)
                if await _sleep(stop, val + 1):
                    raise _Stopped()
                continue
            if kind == "fatal":
                raise _Fatal(val)
            if kind == "skip":
                break
            logger.warning("کپی‌کانال #%s: خطا (تلاش %s/%s): %r", job_id, attempt, _MAX_ATTEMPTS, e)
            if await _sleep(stop, 5 * attempt):
                raise _Stopped()

    if len(ids) == 1:
        return 0, 1
    # فال‌بک: تک‌تک (فقط در مسیرِ خطا؛ ممکنه آلبومِ دارایِ پیامِ خراب از هم جدا بشه)
    ok = bad = 0
    for mid in ids:
        o, b = await _forward_safe(job_id, dst, src, [mid], drop_author, stop)
        ok, bad = ok + o, bad + b
        if await _sleep(stop, _PER_MESSAGE_FALLBACK_DELAY):
            raise _Stopped()
    return ok, bad


async def _run_job(job_id: int) -> None:
    stop = _STOP[job_id]
    live = _LIVE.setdefault(job_id, {})
    try:
        job = await repo.get_job(job_id)
        if not job:
            return
        if job.get("children"):
            # کارِ سازمان‌دهنده‌ی چندکاناله: کپی نمی‌کنه، فقط بچه‌ها رو جمع می‌کنه
            await _coordinator_loop(job_id)
            return
        src = await _resolve(None, job["source_id"], job["source_ref"])
        dst = await _resolve(None, job["dest_id"], job["dest_ref"])
        if src is None or dst is None:
            raise _Fatal("مبدأ یا مقصد پیدا نشد (عضو هستی؟).")
        err = await _validate_pair(src, dst)
        if err:
            raise _Fatal(err)

        copied, skipped, last_id = job["copied"], job["skipped"], job["last_id"]
        w_start, w_count = job["window_start"], job["window_count"]
        if w_start is not None and w_start.tzinfo is None:
            w_start = w_start.replace(tzinfo=dt.timezone.utc)
        drop_author = job["drop_author"]
        watch = bool(job.get("watch"))
        limit = config.CHANNEL_COPY_DAILY_LIMIT
        delay = config.CHANNEL_COPY_DELAY_SECONDS
        live.update(t0=time.time(), copied0=copied, state="شروع")

        while True:
            bad_in_row = 0
            progressed = False
            if _IDLE_WATCH.pop(job_id, False):
                await repo.set_status(job_id, "running", "")
                await _notify(f"🔄 کپی کانال #{job_id} دوباره فعال شد (پیامِ تازه اومد).")
            live["state"] = "در حالِ گشتنِ مبدأ"
            async for batch in iter_batches(
                client.iter_messages(src, min_id=last_id, reverse=True), config.CHANNEL_COPY_BATCH_SIZE
            ):
                if stop.is_set():
                    break
                progressed = True
                if not batch.ids:  # فقط پیام‌های سرویسی
                    skipped += batch.skipped
                    last_id = max(last_id, batch.max_id)
                    await repo.update_progress(
                        job_id, last_id=last_id, copied=copied, skipped=skipped,
                        window_start=w_start, window_count=w_count,
                    )
                    continue

                # سقفِ روزانه
                while True:
                    now = dt.datetime.now(dt.timezone.utc)
                    wait, w_start, w_count = check_window(now, w_start, w_count, limit, len(batch.ids))
                    if wait <= 0:
                        break
                    live["state"] = f"سقفِ روزانه پر شد؛ {int(wait // 60)} دقیقه‌ی دیگه ادامه می‌دم"
                    if await _sleep(stop, min(wait, 60)):
                        break
                if stop.is_set():
                    break

                live["state"] = f"در حالِ کپیِ {len(batch.ids)} پیام"
                ok, bad = await _forward_safe(job_id, dst, src, batch.ids, drop_author, stop)

                copied += ok
                skipped += bad + batch.skipped
                last_id = max(last_id, batch.max_id)
                w_count += ok
                await repo.update_progress(
                    job_id, last_id=last_id, copied=copied, skipped=skipped,
                    window_start=w_start, window_count=w_count,
                )

                bad_in_row = bad_in_row + 1 if ok == 0 else 0
                if bad_in_row >= _MAX_BAD_BATCHES_IN_ROW:
                    raise _Fatal(f"{_MAX_BAD_BATCHES_IN_ROW} دسته‌ی پشتِ‌سرهم ناموفق بود؛ برای جلوگیری از مشکل متوقف شد.")

                live["state"] = f"مکثِ {int(delay)} ثانیه بینِ دسته‌ها"
                if await _sleep(stop, delay):
                    break

            if stop.is_set():
                break
            if not watch:
                break
            # حالتِ «از این به بعد»: اسکن تموم شد؛ حالا منتظرِ پیام‌هایِ تازه می‌مونیم
            if not progressed and job_id not in _IDLE_WATCH:
                _IDLE_WATCH[job_id] = True
                await repo.set_status(job_id, "watching", "")
                await _notify(
                    f"👀 کپی کانال #{job_id} در حالتِ «از این به بعد»: {copied} پیام کپی شد و از "
                    f"الان هر پستِ تازه‌ی {job['source_title']} خودکار کپی می‌شه."
                )
            live["state"] = f"چشم‌به‌راهِ پیام‌هایِ تازه (هر {int(config.CHANNEL_COPY_WATCH_SECONDS)} ثانیه)"
            if await _sleep(stop, config.CHANNEL_COPY_WATCH_SECONDS):
                break

        if stop.is_set():
            await repo.set_status(job_id, "paused", "با دستور متوقف شد")
            await _notify(f"⏸ کپی کانال #{job_id} متوقف شد ({copied} پیام کپی شده). با «{config.PREFIX}کپی‌کانال ادامه» دنبال کن.")
        elif not watch:
            await repo.set_status(job_id, "done", "")
            await _notify(f"✅ کپی کانال #{job_id} تمام شد: {copied} پیام کپی شد" + (f"، {skipped} مورد رد شد." if skipped else "."))

    except _Stopped:
        await repo.set_status(job_id, "paused", "با دستور متوقف شد")
    except _Fatal as e:
        logger.warning("کپی‌کانال #%s متوقف شد: %s", job_id, e)
        await repo.set_status(job_id, "error", str(e))
        await _notify(f"❌ کپی کانال #{job_id} متوقف شد:\n{e}\n(پیشرفت ذخیره شده؛ بعد از رفعِ مشکل «{config.PREFIX}کپی‌کانال ادامه» بزن.)")
    except asyncio.CancelledError:
        await repo.set_status(job_id, "paused", "پروسه بسته شد")
        raise
    except Exception as e:
        logger.exception("کپی‌کانال #%s: خطای پیش‌بینی‌نشده", job_id)
        await repo.set_status(job_id, "error", f"خطای پیش‌بینی‌نشده: {e!r}")
        await _notify(f"❌ کپی کانال #{job_id} با خطای پیش‌بینی‌نشده متوقف شد: {e!r}")
    finally:
        _TASKS.pop(job_id, None)
        _STOP.pop(job_id, None)
        _LIVE.pop(job_id, None)


async def _coordinator_loop(job_id: int) -> None:
    """
    کارِ «سازمان‌دهنده» (کپیِ چند کانال هم‌زمان): خودش پیامی کپی نمی‌کنه؛ فقط
    وضعیتِ بچه‌ها رو جمع می‌کنه و وقتی همه تموم شدن، خبر می‌ده.
    """
    stop = _STOP.get(job_id)
    live = _LIVE.setdefault(job_id, {})
    try:
        job = await repo.get_job(job_id)
        if not job or not job.get("children"):
            return
        children = [int(x) for x in job["children"].split(",") if x.strip().isdigit()]
        live.update(t0=time.time(), copied0=0, state="در حالِ کپیِ چند کانال")
        watch = bool(job.get("watch"))
        while True:
            await asyncio.sleep(10)
            if stop is not None and stop.is_set():
                await repo.set_status(job_id, "paused", "با دستور متوقف شد")
                return
            kids = [await repo.get_job(cid) for cid in children]
            kids = [k for k in kids if k]
            if not kids:
                await repo.set_status(job_id, "error", "کارهای فرزند پیدا نشدن.")
                return
            total = sum(k["copied"] for k in kids)
            skipped = sum(k["skipped"] for k in kids)
            await repo.update_progress(
                job_id, last_id=0, copied=total, skipped=skipped,
                window_start=None, window_count=0,
            )
            running = [k for k in kids if k["status"] in ("running", "watching")]
            live["state"] = f"{len(running)} از {len(kids)} کانال در حالِ کار"
            if not running:
                break
        if stop is not None and stop.is_set():
            await repo.set_status(job_id, "paused", "با دستور متوقف شد")
            return
        done = all(k["status"] in ("done", "watching") for k in kids)
        if not done:
            bad = next(k for k in kids if k["status"] not in ("done", "watching"))
            await repo.set_status(job_id, "error", f"کارِ #{bad['id']} ({bad['source_title']}) متوقف شد: {bad['last_error']}")
            await _notify(f"❌ کپی چندکاناله #{job_id}: کارِ «{bad['source_title']}» متوقف شد:\n{bad['last_error']}")
            return
        if watch:
            await repo.set_status(job_id, "watching", "")
            await _notify(f"👀 کپی چندکاناله #{job_id} به حالتِ «از این به بعد» رفت: {total} پیام کپی شد.")
        else:
            await repo.set_status(job_id, "done", "")
            await _notify(f"✅ کپی چندکاناله #{job_id} تمام شد: {total} پیام کپی شد" + (f"، {skipped} مورد رد شد." if skipped else "."))
    except asyncio.CancelledError:
        await repo.set_status(job_id, "paused", "پروسه بسته شد")
        raise
    except Exception as e:
        logger.exception("کپی‌کانال #%s: خطای سازمان‌دهنده", job_id)
        await repo.set_status(job_id, "error", f"خطای سازمان‌دهنده: {e!r}")
    finally:
        _TASKS.pop(job_id, None)
        _STOP.pop(job_id, None)
        _LIVE.pop(job_id, None)


def _spawn(job_id: int) -> None:
    _STOP[job_id] = asyncio.Event()
    _LIVE[job_id] = {}
    _TASKS[job_id] = asyncio.create_task(_run_job(job_id))


def _spawn_coordinator(job_id: int) -> None:
    _STOP[job_id] = asyncio.Event()
    _LIVE[job_id] = {}
    _TASKS[job_id] = asyncio.create_task(_coordinator_loop(job_id))


def _running_id() -> int | None:
    for jid, t in _TASKS.items():
        if not t.done():
            return jid
    return None


def _status_text(job: dict) -> str:
    live = dict(_LIVE.get(job["id"], {}))
    live["now"] = time.time()
    return format_status(job, live)


# ------------------------------------------------------------ commands ---
async def _merge_saved_names(tokens: list[str]) -> list[str]:
    """
    اسم‌های ذخیره‌شده‌ای که فاصله دارن («اخبار مهم») توی توکن‌ها می‌شن چند تیکه؛
    اینجا تیکه‌های پشتِ‌سرهمی که با هم یک اسمِ ذخیره‌شده می‌سازن دوباره به هم می‌چسبن.
    """
    if len(tokens) < 2:
        return tokens
    try:
        rows = await repo.list_targets()
    except Exception:
        logger.debug("لیستِ اسم‌ها خونده نشد", exc_info=True)
        return tokens
    names = {_norm_search(r["name"]) for r in rows}
    if not names:
        return tokens
    out: list[str] = []
    i = 0
    while i < len(tokens):
        merged = False
        for span in range(min(3, len(tokens) - i), 1, -1):  # حداکثر سه‌کلمه‌ای
            cand = " ".join(tokens[i:i + span])
            if _norm_search(cand) in names:
                out.append(cand)
                i += span
                merged = True
                break
        if not merged:
            out.append(tokens[i])
            i += 1
    return out


async def _channel_from_reply(reply):
    """
    کانالِ مبدأ از پیامِ ریپلای‌شده:
      ۱) اگر خودِ پیام از یک کانال اومده (فوروارد) → همون کانال
      ۲) وگرنه شناسه‌ی کانال از هدرِ فوروارد (`fwd_from.from_id`) — حتی اگه
         `get_sender()` کار نکنه (پیوی/سشنِ تازه) این مسیر قطعی‌ست
      ۳) وگرنه لینک‌های کانالی که توی متنِ پیام هست (مثلِ معرفیِ کانالِ بعدی)
    """
    if reply is None:
        return None
    if getattr(reply, "fwd_from", None) is None and _is_channel_like(reply):
        return reply
    try:
        ent = await reply.get_sender()
    except Exception:
        logger.debug("get_sender روی پیامِ ریپلای ناموفق بود", exc_info=True)
        ent = None
    if _is_channel_like(ent):
        return ent
    # هدرِ فوروارد: شناسه‌ی کانالِ مبدأ
    fwd = getattr(reply, "fwd_from", None)
    peer = getattr(fwd, "from_id", None) if fwd is not None else None
    inner = getattr(peer, "channel_id", None) or getattr(peer, "chat_id", None)
    if inner:
        ent = await _resolve_source_by_id(int(f"-100{inner}")) or await _resolve_source_by_id(int(inner))
        if ent is not None:
            return ent
    # متنِ پیام: ممکنه لینکِ کانال داخلش باشه (بدونِ هیچ اتصالی — فقط بررسی می‌کنیم)
    links = extract_protected_links(
        getattr(reply, "message", "") or "", getattr(reply, "entities", None)
    )
    if links:
        try:
            found, _why = await _pick_source_by_link(links)
        except Exception:
            logger.warning("حلِ لینکِ داخلِ پیامِ ریپلای ناموفق بود", exc_info=True)
            found = None
        if found is not None:
            return found
    return None


async def _resolve_start_pair(src_raw: str, dst_raw: str, reply):
    """
    (مبدأها, مقصد, خطا) — مبدأ می‌تونه چند تا با کاما باشه، و اسم‌های ذخیره‌شده
    («کپی‌کانال ذخیره ...») هم قبولن. مقصد هم آدرس/اسم/ریپلای.
    """
    src_specs = [s for s in re.split(r"[,\u060c]+", src_raw) if s.strip()]
    if not src_specs:
        return [], None, "مبدأ خالیه."
    reply_mode = src_specs == ["__reply__"]

    dst = None
    if not dst_raw:
        # مقصد از ریپلای: پستی که داخلِ خودِ کانالِ مقصد نوشته شده (کانالِ خصوصی)
        peer = getattr(reply, "peer_id", None) if reply is not None else None
        inner = getattr(peer, "channel_id", None) or getattr(peer, "chat_id", None)
        if inner:
            dst = await _resolve_source_by_id(int(f"-100{inner}")) or await _resolve_source_by_id(int(inner))
        if dst is None:
            return [], None, (
                "مقصد پیدا نشد: آدرسِ مقصد را بده، یا روی پستی که **داخلِ کانالِ مقصد** نوشته شده ریپلای کن."
            )
    else:
        saved_dst = await repo.get_target(dst_raw)
        if saved_dst is not None:
            dst = await _resolve_source_by_id(int(saved_dst["chat_id"]))
        else:
            try:
                dst_ref = parse_chat_ref(dst_raw)
            except ValueError as e:
                return [], None, f"مقصد: {e}"
            dst = await _resolve(dst_ref, None, dst_raw)
        if dst is None:
            return [], None, "کانالِ مقصد پیدا نشد (باید عضوش باشی)."

    resolved: list[tuple[object, str]] = []
    for spec in src_specs:
        spec = spec.strip()
        if reply_mode:
            # مبدأ = همان کانالی که پستِ ریپلای‌شده ازش آمده (یا لینکِ داخلش)
            ent = await _channel_from_reply(reply)
            if ent is None:
                # اگه لینکِ دعوتِ کانالِ ناشناسی بود، دلیلش رو بگو
                links = extract_protected_links(
                    getattr(reply, "message", "") or "", getattr(reply, "entities", None)
                )
                reason = ""
                if links:
                    try:
                        _f, why = await _pick_source_by_link(links)
                        reason = why or ""
                    except Exception:
                        logger.debug("حلِ لینک برای پیامِ خطا ناموفق بود", exc_info=True)
                return [], None, reason or (
                    "مبدأ پیدا نشد: روی یک پست از **کانالِ مبدأ** ریپلای کن، یا آدرسش را بده "
                    "(`.کپی‌کانال شروع @مبدأ @مقصد`)."
                )
            resolved.append((ent, str(tl_utils.get_peer_id(ent))))
            continue
        # «پوشه:N» / «پوشه:اسم» / «folder:N» → همه‌ی کانال/گروه‌های اون پوشه
        m = re.fullmatch(r"(?:پوشه|folder)\s*[:：]\s*(.+)", spec, re.IGNORECASE)
        if m:
            dst_id = tl_utils.get_peer_id(dst) if dst is not None else 0
            try:
                extra = await _targets_for_scope(f"folder:{m.group(1).strip()}", dst_id)
            except ValueError as e:
                return [], None, str(e)
            resolved.extend((e2, r2) for e2, r2, _t in extra)
            continue
        saved = await repo.get_target(spec)
        if saved is not None:
            ent = await _resolve_source_by_id(int(saved["chat_id"]))
            if ent is not None:
                resolved.append((ent, ""))
                continue
        ent, ref = await _source_from_anchor(_answer_ref(spec, reply))
        if ent is None:
            # شاید کاربر روی پستی از همون کانال ریپلای کرده (کانالِ خصوصیِ فورواردشده
            # یا پستی که لینکِ کانال توش هست)
            fwd_ent = await _channel_from_reply(reply)
            if fwd_ent is not None:
                resolved.append((fwd_ent, ""))
                continue
            links = extract_protected_links(
                getattr(reply, "message", "") or "", getattr(reply, "entities", None)
            )
            if links:
                try:
                    _f, why = await _pick_source_by_link(links)
                    if why:
                        return [], None, why
                except Exception:
                    logger.debug("حلِ لینک برای پیامِ خطا ناموفق بود", exc_info=True)
            return [], None, ref
        resolved.append((ent, ref))

    dst_pid = tl_utils.get_peer_id(dst)
    resolved = [(e, r) for e, r in resolved if tl_utils.get_peer_id(e) != dst_pid]
    if not resolved:
        return [], None, "مبدأ و مقصد یکی‌ان."
    return resolved, dst, ""


def _looks_like_ref(tok: str) -> bool:
    """آیا این توکن شکلِ آدرسِ کانال داره (@user / آیدی / لینک t.me / +hash)؟"""
    t = (tok or "").strip()
    low = t.lower()
    if not t:
        return False
    if low.startswith(("@", "+", "joinchat/", "t.me/", "https://t.me/", "http://t.me/", "telegram.me/")):
        return True
    if "/" in t:
        return True
    return t.lstrip("-").isdigit()


def _answer_ref(tok: str, reply=None):
    """
    یک آدرس (مبدأ/مقصد) رو از توکن بساز:
      • «+hash» / «joinchat/hash» / لینکِ t.me/c/... → با ریپلای به خودِ پیامِ کانال
      • «اسمِ ذخیره‌شده» → با «ذخیره» به یک کانال وصل شده (repo)
      • وگرنه همون ورودیِ معمولی (@user / آیدی / t.me/...)
    """
    low = tok.lower()
    if low.startswith(("+", "joinchat/")) or "/c/" in low or low.startswith(("t.me/c/", "https://t.me/c/")):
        return tok
    if reply is not None:
        if getattr(reply, "id", None):
            if low.startswith(("t.me/", "https://t.me/")):
                return tok
            if tok.startswith("@"):
                split = tok.split("/", 1)
                return f"{split[0]}/{reply.id}"
            ent = getattr(reply, "peer_id", None)
            inner = getattr(ent, "channel_id", None) or getattr(ent, "chat_id", None)
            if inner:
                return f"t.me/c/{inner}/{reply.id}"
    return tok


async def _resolve_source_by_id(chat_id: int):
    """کانال از «شناسه‌ی کامل» (‎-100…‎) — تلاش‌های مختلف."""
    for kind, ref in (
        ("id", chat_id),
        ("id", int(f"-100{abs(chat_id)}")),
        ("id", abs(chat_id)),
        ("id", int(f"-{abs(chat_id)}")),
    ):
        ent = await _resolve((kind, ref), None, "")
        if ent is not None:
            return ent
    return None


async def _pick_source_by_link(links: list[dict]):
    """
    لینکِ کانال → entity، به ترتیبِ اولویت:
      ۱) t.me/c/<شناسه> → با اسکنِ لیستِ چت‌ها یا آیدی‌های عددی
      ۲) t.me/<یوزرنیم>
      ۳) لینکِ دعوت: اول اسمش خونده می‌شه و کانالِ هم‌نام توی چت‌های خودت
         جستجو می‌شه (کاربر عملاً عضوش است)؛ وگرنه اسمش برگردانده می‌شه تا
         به کاربر گفته بشه باید عضو بشه. هیچ‌وقت خطا پرت نمی‌کنه.
    """
    for it in links:
        kind, ref, mid = it["kind"], it["ref"], it["message_id"]
        if kind == "private":
            short = int(ref.split("/")[-1])
            ent = await _find_by_protected_link(short) or await _find_channel_by_inner_id(
                short, int(f"-100{short}")
            )
            if ent is not None:
                return ent, f"از لینکِ خصوصی ({ref})"
        elif kind == "public":
            try:
                parsed = parse_chat_ref(ref)
            except ValueError:
                parsed = None
            if parsed is not None:
                ent = await _resolve(parsed, None, ref)
                if ent is not None:
                    return ent, f"از لینک ({ref})"
        else:  # invite
            # مهم: parse_chat_ref روی «+hash» خطا می‌ده؛ اینجا نباید پرت بشه
            name = await _check_invite(it.get("hash") or "")
            if name:
                ent = await _find_channel_by_name(name)
                if ent is not None:
                    return ent, f"از لینکِ دعوتِ «{name}»"
                return None, f"لینکِ دعوتِ «{name}» — اول باید عضوش باشی"
            return None, f"لینکِ دعوتِ «{ref}» — اول باید عضوش باشی"
    return None, ""


async def _find_channel_by_name(name: str, exact_first: bool = True):
    """
    کانال/گروه از روی «اسم» بینِ چت‌های خودت.
    اول تطبیقِ دقیقِ نرمال‌شده، بعد تطبیقِ جزئی؛ اگه چند تا خورد و هیچ‌کدام دقیق نبود،
    چیزی برنمی‌گردونه (بهتر از انتخابِ اشتباه).
    """
    want = _norm_search(name)
    if not want:
        return None
    try:
        found = await _search_targets("", limit=500)   # همه‌ی کانال/گروه‌های لیستِ چت‌ها
    except Exception:
        logger.debug("جستجویِ اسمیِ کانال ناموفق بود", exc_info=True)
        return None
    exact = [ent for ent, _pid, title in found if _norm_search(title) == want]
    if exact:
        return exact[0]
    if not exact_first:
        near = [ent for ent, _pid, title in found if want in _norm_search(title)]
        if len(near) == 1:
            return near[0]
    near = [ent for ent, _pid, title in found if want in _norm_search(title)]
    return near[0] if len(near) == 1 else None


async def _source_from_anchor(anchor: str, reply=None):
    """
    یک ارجاعِ مبدأ → (entity, refِ قابلِ ذخیره).
    پشتیبانی: همان parse_chat_ref + «t.me/c/<شناسه>» + «t.me/c/<شناسه>/<شماره>» + ریپلای.
    """
    anchor = (anchor or "").strip()
    low = anchor.lower()
    if "/c/" in low or low.startswith("t.me/c/"):
        m = re.search(r"/c/(\d+)(?:/(\d+))?", anchor)
        if m:
            target_id = int(m.group(1))
            ent = await _find_by_protected_link(target_id) or await _find_channel_by_inner_id(
                target_id, int(f"-100{target_id}")
            )
            if ent is None:
                return None, "کانالِ خصوصیِ این لینک پیدا نشد (عضو هستی؟)"
            mid = int(m.group(2) or 0)
            return ent, f"t.me/c/{target_id}" + (f"/{mid}" if mid else "")
    try:
        parsed = parse_chat_ref(anchor)
    except ValueError:
        parsed = None
    if parsed:
        ent = await _resolve(parsed, None, anchor)
        if ent is not None:
            return ent, anchor
    # لینکِ دعوت
    if low.startswith("joinchat/") or low.startswith("+"):
        return None, f"⚠️ «{anchor}» لینکِ دعوتِ خصوصیه؛ این لینک‌ها به entity تبدیل نمی‌شن."
    return None, f"«{anchor}» پیدا نشد (عضو هستی؟)"


async def _forwarded_source(event):
    """اگر ارجاع داده نشده و فورواردِ کانالی ریپلای شده باشه → خودِ کانالِ مبدأیِ فوروارد."""
    reply = await event.get_reply_message()
    if reply is None:
        return None, "", None
    fwd = getattr(reply, "fwd_from", None)
    src = reply
    if fwd is not None:
        try:
            src = await reply.get_sender()
        except Exception:
            src = None
    if src is None or not _is_channel_like(src):
        return None, "", reply
    return src, f"fwd:{tl_utils.get_peer_id(src)}", reply


@client.on(events.NewMessage(outgoing=True, pattern=pat(["کپی‌کانال", "کپی_کانال", "کپیکانال", "copychannel"])))
async def channel_copy_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    tokens = arg.split()
    sub = tokens[0].lower() if tokens else ""
    rest = tokens[1:]

    if sub in ("راهنما", "help"):
        return await event.edit(USAGE)

    # ---- کمک: پیدا کردنِ کانال‌های خصوصی -------------------------------------
    if sub in ("پیدا", "جستجو", "find", "search"):
        query = " ".join(rest)
        await event.edit(f"🔎 دارم بین چت‌ها دنبالِ «{query}» می‌گردم… (چند ثانیه)")
        try:
            found = await _search_targets(query, limit=30)
        except Exception as e:
            logger.exception("جستجوی چت‌ها ناموفق بود")
            return await event.edit(f"❌ خطا در جستجو: {e}")
        if not found:
            return await event.edit(
                "چیزی پیدا نشد. با بخشی از اسم (فارسی هم می‌شه) یا یوزرنیم یا آیدی امتحان کن."
            )
        lines = ["🔎 **کانال/گروه‌های پیدا‌شده:**"]
        for ent, pid, title in found:
            uname = f" @{ent.username}" if getattr(ent, "username", None) else ""
            lines.append(f"• **{title}**{uname}\n  آیدی: `{pid}`")
        lines.append("\nبرای کپی: `.کپی‌کانال شروع` + ریپلای روی همین پیام، یا آیدی رو بده.")
        return await event.edit("\n".join(lines))

    if sub in ("پوشه‌ها", "folders"):
        await event.edit("📁 دارم پوشه‌ها رو می‌خونم…")
        names = await _folder_names()
        if not names:
            return await event.edit(
                "پوشه‌ای پیدا نشد (یا این نسخه‌ی Telethon نمی‌تونه بخونه). "
                "می‌تونی به‌جای اسمِ پوشه، اسمِ کانال‌ها رو جدا بدی: `.کپی‌کانال شروع @a,@b @dst`"
            )
        lines = ["📁 **پوشه‌ها:**"]
        for fid, name in sorted(names.items()):
            lines.append(f"• «{name}» — شماره: `{fid}`")
        lines.append("\nاستفاده: `.کپی‌کانال شروع پوشه:1 @مقصد از 1403/05/01`")
        return await event.edit("\n".join(lines))

    if sub in ("ذخیره", "save"):
        if not rest:
            return await event.edit("مثال: `.کپی‌کانال ذخیره اخبار @khabar_channel`")
        # آخرین توکن اگه شکلِ آدرس داشته باشه آدرسه، بقیه اسمِ دلخواهه
        anchor = ""
        name_tokens = list(rest)
        if len(rest) >= 2 and _looks_like_ref(rest[-1]):
            anchor, name_tokens = rest[-1], rest[:-1]
        elif len(rest) == 1 and _looks_like_ref(rest[0]):
            return await event.edit(
                "اسمِ دلخواه رو هم بده: `.کپی‌کانال ذخیره اخبار @khabar_channel`"
            )
        name = " ".join(name_tokens).strip()
        if not name:
            return await event.edit("اسمِ دلخواه خالیه.")
        reply = await event.get_reply_message()
        ent, ref = await _source_from_anchor(anchor, reply) if anchor else (None, "")
        if ent is None:
            ent = await _channel_from_reply(reply)
            ref = "" if ent is not None else ref
        if ent is None:
            return await event.edit(f"⚠️ {ref or 'کانالی پیدا نشد — آدرس بده یا روی پیامِ کانال ریپلای کن.'}")
        pid = tl_utils.get_peer_id(ent)
        await repo.save_target(name, pid, _title(ent))
        return await event.edit(f"💾 ذخیره شد: «{name}» → {_title(ent)}\nآیدی: `{pid}`\nالان می‌تونی بنویسی: `.کپی‌کانال شروع {name} @مقصد`")

    if sub in ("اسم‌ها", "targets"):
        rows = await repo.list_targets()
        if not rows:
            return await event.edit("اسمی ذخیره نشده. مثال: `.کپی‌کانال ذخیره اخبار @ch`")
        return await event.edit(
            "💾 **اسم‌های ذخیره‌شده:**\n"
            + "\n".join(f"• «{r['name']}» → {r['title'] or r['chat_id']} (`{r['chat_id']}`)" for r in rows)
        )

    if sub in ("وضعیت", "status", ""):
        job = await (repo.get_job(int(rest[0])) if rest and rest[0].isdigit() else repo.get_latest_job())
        if not job:
            return await event.edit(USAGE)
        return await event.edit(_status_text(job))

    if sub in ("لیست", "list"):
        jobs = await repo.list_jobs(10)
        if not jobs:
            return await event.edit("هنوز کاری ثبت نشده.")
        lines = ["📋 **کارهای کپی کانال**"]
        for j in jobs:
            lines.append(
                f"#{j['id']} {j['source_title'] or j['source_id']} → {j['dest_title'] or j['dest_id']} "
                f"| {j['copied']} پیام | {j['status']}"
            )
        return await event.edit("\n".join(lines))

    if sub in ("توقف", "stop"):
        if rest and rest[0].isdigit():
            jid = int(rest[0])
            if jid not in _TASKS:
                return await event.edit(f"کار #{jid} الان در حالِ اجرا نیست.")
        else:
            jid = _running_id()
        if jid is None:
            return await event.edit("کارِ فعالی نیست.")
        _STOP[jid].set()
        return await event.edit(f"⏸ درخواستِ توقفِ کار #{jid} ثبت شد (بعد از دسته‌ی جاری متوقف می‌شه).")

    if sub in ("حذف", "delete"):
        if not rest or not rest[0].isdigit():
            return await event.edit("شماره‌ی کار رو بده: `.کپی‌کانال حذف 3`")
        jid = int(rest[0])
        if jid in _TASKS:
            return await event.edit("این کار در حالِ اجراست؛ اول «توقف» بزن.")
        ok = await repo.delete_job(jid)
        return await event.edit("🗑 حذف شد." if ok else "کاری با این شماره نیست.")

    if sub in ("ادامه", "resume"):
        if rest and rest[0].isdigit():
            job = await repo.get_job(int(rest[0]))
        else:
            job = await repo.get_latest_job()
        if not job:
            return await event.edit("کاری برای ادامه پیدا نشد.")

        busy = _running_id()
        if busy is not None and busy != job["id"]:
            return await event.edit("یک کپی در حالِ اجراست؛ همزمان فقط یکی مجازه (وضعیت/توقف).")

        # کارِ گروهی (چند کانال/پوشه): خودش کپی نمی‌کنه؛ بچه‌ها رو ادامه می‌ده
        if job.get("children"):
            kids = await repo.list_children(job["id"])
            pending = [k for k in kids if k["status"] != "watching"]
            if not pending:
                return await event.edit(
                    f"کار #{job['id']} در حالتِ «از این به بعد» فعاله و پیام‌های تازه رو خودش می‌گیره."
                )
            for k in pending:
                await repo.set_status(k["id"], "running", "")
                _spawn(k["id"])
            if job["status"] not in ("running",) or job["id"] not in _TASKS:
                await repo.set_status(job["id"], "running", "")
                _spawn_coordinator(job["id"])
            return await event.edit(
                f"▶️ کار #{job['id']}: {len(pending)} کانال از پیامِ آخرشون به بعد ادامه می‌دن "
                f"(پیام‌های تازه هم کپی می‌شن)."
            )

        if job["status"] == "watching" and job["id"] in _TASKS:
            return await event.edit(
                f"👀 کار #{job['id']} از قبل در حالتِ «از این به بعد» فعاله و پیام‌های تازه رو "
                f"خودکار کپی می‌کنه (هر {int(config.CHANNEL_COPY_WATCH_SECONDS)} ثانیه چک می‌شه)."
            )

        # کپیِ تمام‌شده/متوقف‌شده → از پیامِ آخرش به بعد؛ یعنی فقط پست‌های تازه
        await repo.set_status(job["id"], "running", "")
        _spawn(job["id"])
        tail = (
            "پیام‌های تازه‌ی بعدش کپی می‌شن"
            if job["status"] == "done"
            else "ادامه‌ی کپی از همون‌جا"
        )
        return await event.edit(
            f"▶️ کار #{job['id']} از پیامِ #{job['last_id'] + 1} به بعد ادامه پیدا کرد ({tail}).\n"
            f"• پیشرفت: `{config.PREFIX}کپی‌کانال وضعیت {job['id']}`"
        )

    # ---------------------------------------------------------------- شروع ---
    watch = False
    if sub in ("شروع", "start"):
        tokens_for_start = rest
    else:
        tokens_for_start = tokens
    tokens_for_start = [t for t in tokens_for_start if t not in ("ازاین‌بعد", "ازاینبعد", "ازاین-بعد", "watch")]
    if len(tokens_for_start) != len(rest if sub in ("شروع", "start") else tokens):
        watch = True

    # اسم‌های ذخیره‌شده‌ی چندکلمه‌ای («اخبار مهم») رو به هم می‌چسبونیم و بعد
    # اگه لازم شد، جدا‌کردنِ مبدأ/مقصد رو با کاندیدهای مختلف امتحان می‌کنیم.
    merged_tokens = await _merge_saved_names(list(tokens_for_start))
    cands = [merged_tokens]
    if merged_tokens == list(tokens_for_start) and len(tokens_for_start) >= 2:
        cands += [c for c in start_variants(list(tokens_for_start)) if c != merged_tokens]
    if len(merged_tokens) == 1 and len(tokens_for_start) > 1:
        cands = [list(tokens_for_start)]

    reply = await event.get_reply_message()

    if _running_id() is not None:
        return await event.edit("یک کپی در حالِ اجراست؛ همزمان فقط یکی مجازه (وضعیت/توقف).")

    msg = None
    resolved = None
    dst = None
    last_err = ""
    src_raw = dst_raw = ""
    from_id, from_date, drop_author = 0, None, True
    for cand in cands:
        try:
            (src_raw, dst_raw, from_id, from_date, drop_author, marks, from_reply) = parse_start_any(list(cand))
        except ValueError as e:
            last_err = str(e)
            continue
        if msg is None:
            msg = await event.edit("🔎 دارم کانال‌ها رو بررسی می‌کنم… (ممکنه تا ۳۰ ثانیه طول بکشه)")
        if from_reply and reply is None:
            # دستور یک آدرس داره ولی ریپلایی نیست؛ هیچ کاندید دیگه‌ای معنی نداره
            return await event.edit(
                "⚠️ این دستور یک آدرس داره (پس همان «مقصد» است) و باید روی یک پست از **کانالِ مبدأ** "
                "ریپلای کنی.\n"
                f"یا هر دو آدرس را بده: `{config.PREFIX}کپی‌کانال شروع @مبدأ @مقصد`"
            )
        try:
            if from_reply:
                # «شروع @مقصد» + ریپلای: آدرسِ داده‌شده مقصد است، مبدأ از پستِ ریپلای‌شده
                pair = await _resolve_start_pair("__reply__", dst_raw, reply)
            else:
                pair = await _resolve_start_pair(src_raw, dst_raw, reply)
        except ValueError as e:
            # ورودیِ نامعتبر (مثلاً لینکِ دعوت) → پیامِ روشن، نه «خطای داخلی»
            return await msg.edit(f"⚠️ {e}")
        except Exception as e:
            logger.exception("خطا در resolve کردنِ کانال‌ها")
            return await msg.edit(f"❌ خطا در پیدا کردنِ کانال‌ها: {e}")
        resolved, dst, err = pair
        if not err:
            break
        last_err = err
        resolved = None

    if resolved is None or dst is None:
        if msg is None:
            return await event.edit(f"⚠️ {last_err}\n\n{USAGE}")
        return await msg.edit(f"⚠️ {last_err}")

    assert msg is not None
    # اعتبارسنجیِ اولیه‌ی مقصد با اولین مبدأ (فقط وقتی یک مبدأ داریم؛ وگرنه بعضی
    # کانال‌ها ممکنه perms برنگردونن و نباید کلِ کار رو خراب کنه)
    err = await _validate_pair(resolved[0][0], dst)
    if err and len(resolved) <= 1:
        return await msg.edit(f"⛔ {err}")
    dst_pid = tl_utils.get_peer_id(dst)

    # مرزهای تاریخ/شماره (برای هر مبدأ جدا حساب می‌شه)
    if from_date is not None:
        await msg.edit(
            f"🔎 دارم اولین پیامِ **{format_from_date(from_date)}** رو توی {len(resolved)} کانال پیدا می‌کنم… (تا یک دقیقه)"
        )
    jobs = []
    notes = []
    for src, ref in resolved:
        sid = tl_utils.get_peer_id(src)
        start_after = from_id
        this_date = from_date
        # فقط در حالتِ «از این به بعد» از آخرین نقطه‌ی کپیِ قبلیِ همین جفت‌کانال
        # ادامه می‌دیم (که همون کانال دو بار از اول کپی نشه). کپیِ معمولی مثلِ قبل
        # از ابتدا/تاریخِ خواسته‌شده شروع می‌شه.
        if watch and from_id == 0 and from_date is None:
            last_id, prev_job = await repo.last_progress(sid, dst_pid)
            if prev_job is not None and last_id > 0:
                start_after = last_id
                notes.append(f"• {_title(src)}: از پیامِ #{last_id + 1} (ادامه‌ی کپیِ قبلی)")
        if this_date is not None:
            try:
                found_id = await _start_id_by_date(src, this_date, start_after=start_after)
            except Exception as e:
                logger.exception("خطا در پیدا کردنِ مرزِ تاریخ")
                return await msg.edit(f"❌ خطا در پیدا کردنِ پیام‌هایِ این تاریخ ({_title(src)}): {e}")
            if not found_id:
                notes.append(f"• {_title(src)}: از این تاریخ پیامی نبود → رد شد")
                continue
            start_after = int(found_id) - 1
            notes.append(f"• {_title(src)}: شروع از {format_from_date(this_date)} (پیامِ #{found_id})")
        total = 0
        try:
            total = int(getattr(await client.get_messages(src, limit=0), "total", 0) or 0)
            if start_after > 0:
                before = int(getattr(await client.get_messages(src, max_id=start_after + 1, limit=0), "total", 0) or 0)
                if 0 <= before < total:
                    total -= before
        except Exception:
            logger.debug("total شمارش نشد", exc_info=True)

        job = await repo.create_job(
            source_id=sid, source_title=_title(src), source_ref=ref or str(sid),
            dest_id=dst_pid, dest_title=_title(dst), dest_ref=dst_raw,
            last_id=start_after, total_hint=total, drop_author=drop_author,
            from_date=this_date, watch=watch,
        )
        jobs.append(job)

    if not jobs:
        return await msg.edit("⚠️ هیچ کاری ساخته نشد (هیچ مبدأیی از این تاریخ پیام نداشت).")

    # حالتِ گروهی: یک کارِ «سازمان‌دهنده» که هیچ پیامی کپی نمی‌کنه و فقط بچه‌ها رو نگه می‌داره
    parent = None
    if len(jobs) > 1:
        parent = await repo.create_job(
            source_id=jobs[0]["source_id"], source_title=f"{len(jobs)} کانالِ مبدأ",
            source_ref=src_raw, dest_id=dst_pid, dest_title=_title(dst), dest_ref=dst_raw,
            last_id=0, total_hint=0, drop_author=drop_author, from_date=from_date, watch=watch,
        )
        await repo.set_job_meta(parent["id"], children=",".join(str(j["id"]) for j in jobs))
        await repo.set_status(parent["id"], "running", "")

    for j in jobs:
        _spawn(j["id"])
    if parent is not None:
        _spawn_coordinator(parent["id"])

    per_hour = int(config.CHANNEL_COPY_BATCH_SIZE * 3600 / (config.CHANNEL_COPY_DELAY_SECONDS + 1))
    limit = config.CHANNEL_COPY_DAILY_LIMIT
    cap = f"سقفِ روزانه {limit} پیام" if limit else "بدونِ سقفِ روزانه"
    head = f"▶️ کپی کانال #{parent['id'] if parent else jobs[0]['id']} شروع شد"
    extra = ("\n" + "\n".join(notes)) if notes else ""
    await event.edit(
        f"{head}\n"
        f"• مقصد: {_title(dst)}\n"
        f"• {len(jobs)} کانالِ مبدأ{extra}\n"
        f"• دسته‌های {config.CHANNEL_COPY_BATCH_SIZE}تایی، مکثِ {int(config.CHANNEL_COPY_DELAY_SECONDS)} ثانیه "
        f"(حداکثر ~{per_hour} پیام در ساعت؛ {cap})"
        + ("\n• حالتِ «از این به بعد»: ‌پیام‌هایِ تازه هم خودکار کپی می‌شن 👀" if watch else "")
        + f"\n• پیشرفت: `{config.PREFIX}کپی‌کانال وضعیت` | توقف: `{config.PREFIX}کپی‌کانال توقف`"
    )
