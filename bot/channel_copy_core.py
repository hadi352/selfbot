"""هسته‌ی منطقیِ «کپی کانال» (`.کپی‌کانال`) — بدونِ وابستگی به Telethon/SQLAlchemy.

همه‌ی منطقِ خالص (پارس ورودی، پارسِ تاریخِ شمسی/میلادی، پیدا کردنِ اولین پیامِ
یک تاریخ، دسته‌بندیِ پیام‌ها با حفظِ آلبوم، طبقه‌بندیِ
خطاهای تلگرام، پنجره‌ی سقفِ روزانه، متنِ وضعیت) اینجاست تا بدونِ اتصال به
تلگرام قابلِ تست باشه. خودِ ارسال/اتصال در handlers/channel_copy.py انجام می‌شه.

محدودیت‌های تلگرام که اینجا رعایت می‌شن:
  • هر درخواستِ forwardMessages حداکثر ۱۰۰ پیام (ما به‌طورِ پیش‌فرض ۲۰).
  • آلبوم‌ها (grouped_id) هرگز بینِ دو درخواست نصف نمی‌شن.
  • FloodWait / SlowMode: دقیقاً به‌اندازه‌ی خواسته‌شده صبر می‌کنیم.
  • خطاهای قطعی (دسترسی/PeerFlood/محتوای محافظت‌شده) → توقف، نه دورزدن.
  • سقفِ روزانه‌ی پیامِ کپی‌شده (پنجره‌ی ۲۴ ساعته).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

TELEGRAM_MAX_FORWARD_BATCH = 100
DAY = dt.timedelta(hours=24)


# ------------------------------------------------------------ parsing ---
_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_TME_RE = re.compile(r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(.+)$", re.IGNORECASE)


def split_ref(raw: str) -> tuple[str, int]:
    """
    «@channel/12345» → ("@channel", 12345). شماره‌ی پیامِ چسبیده به آدرس جدا می‌شه
    تا بشه اولِ کپیِ یک کانال رو دقیق مشخّص کرد.
    بعد از اسلشِ آخر فقط اگه همه‌ی کاراکترها رقم باشن (ارقامِ فارسی هم می‌شن).
    ⚠️ «t.me/c/<شناسه>» و «t.me/c/<شناسه>/<شماره>» دست‌نخورده می‌مونن: اونجا عدد
    خودِ شناسه‌ی کانالِ خصوصیه، نه شماره‌ی پیام.
    """
    s = to_ascii_digits((raw or "").strip())
    m = re.search(r"/c/(\d+)(?:/(\d+))?$", s)
    if m:
        # لینکِ کانالِ خصوصی: شناسه‌ی کانال دست‌نخورده می‌مونه، فقط شماره‌ی پیامِ آخر جدا می‌شه
        return s[: m.end(1)], int(m.group(2) or 0)
    if "/" not in s:
        return s, 0
    head, _, tail = s.rpartition("/")
    if not head or not tail.isdigit():
        return s, 0
    return head, int(tail)


def parse_chat_ref(raw: str) -> tuple[str, Any]:
    """
    ورودیِ کاربر برای مبدأ/مقصد → ("username", str) یا ("id", int).
    پشتیبانی: @user ، user ، t.me/user ، t.me/user/123 ، t.me/c/<id>/<msg> ،
    شناسه‌ی عددی (‎-100…‎ یا بدونِ پیشوند)، و «@user/123» (شماره‌ی پیامِ چسبیده —
    با split_ref جدا می‌شه). لینکِ دعوتِ خصوصی (t.me/+…) قابلِ
    استفاده نیست چون بدونِ عضویت entity نمی‌ده → ValueError با راهنما.
    """
    s = (raw or "").strip().strip("<>").strip()
    if not s:
        raise ValueError("آدرسِ کانال خالیه")

    m = _TME_RE.match(s)
    if m:
        path = m.group(1).split("?")[0].strip("/")
        parts = path.split("/")
        first = parts[0]
        if first.startswith("+") or first.lower() == "joinchat":
            raise ValueError(
                "لینکِ دعوتِ خصوصی پشتیبانی نمی‌شه. اول با اکانتت عضوِ کانال شو، "
                "بعد یوزرنیم یا شناسه‌ی عددیِ کانال رو بده."
            )
        if first.lower() == "c" and len(parts) >= 2 and parts[1].isdigit():
            return "id", int(f"-100{parts[1]}")
        s = first

    if s.startswith("@"):
        s = s[1:]
    if re.fullmatch(r"-?\d+", s):
        return "id", int(s)
    if _USERNAME_RE.match(s):
        return "username", s
    raise ValueError(f"«{raw}» آدرسِ معتبرِ کانال نیست (از @username یا شناسه‌ی عددی استفاده کن)")


_WITH_AUTHOR_FLAGS = {"با‌نام", "بانام", "با_نام", "withauthor", "with-author", "with_author", "نام"}
_FROM_FLAGS = {"از", "from"}
_TIME_KEYWORDS = {"ساعت", "وقت", "time", "at"}
# «امروز/دیروز» نسبت به «الان» به وقتِ کاربر (یعنی now که صداکننده می‌ده)
_RELATIVE_DATES = {"امروز": 0, "دیروز": -1, "پریروز": -2, "today": 0, "yesterday": -1}


def to_ascii_digits(s: str) -> str:
    """ارقامِ فارسی/عربی (۱۴۰۳، ١٤٠٣) رو به لاتین تبدیل می‌کنه."""
    return (s or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


# تبدیلِ تقویم (همون الگوریتمِ bot/handlers/extras.py؛ اینجا کپیه چون این ماژول
# باید بدونِ Telethon/SQLAlchemy هم لود بشه — تست‌ها مستقیم همین فایل رو می‌خونن)
def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    )
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    jy += 1595
    days = (
        -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
        + ((jm - 1) * 31 if jm < 7 else ((jm - 7) * 30 + 186))
    )
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    sal_a = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    for i in range(1, 13):
        if gd <= sal_a[i]:
            gm = i
            break
        gd -= sal_a[i]
    return gy, gm, gd


def _make_date(y: int, mo: int, d: int) -> dt.date:
    """سالِ ۱۶۰۰ تا ۲۱۹۹ = میلادی • سالِ ۱۱۰۰ تا ۱۵۹۹ = شمسی."""
    if 1600 <= y <= 2199:
        try:
            return dt.date(y, mo, d)
        except ValueError:
            raise ValueError(f"تاریخِ میلادیِ نامعتبره: {y}/{mo}/{d}")
    if 1100 <= y <= 1599:
        try:
            gy, gm, gd = jalali_to_gregorian(y, mo, d)
            if gregorian_to_jalali(gy, gm, gd) != (y, mo, d):
                raise ValueError
        except ValueError:
            raise ValueError(f"تاریخِ شمسیِ نامعتبره: {y}/{mo}/{d}")
        return dt.date(gy, gm, gd)
    raise ValueError(f"سالِ «{y}» نامعتبره (شمسی: ۱۱۰۰ تا ۱۵۹۹ • میلادی: ۱۶۰۰ تا ۲۱۹۹)")


def parse_date_arg(raw: str) -> dt.date | None:
    """
    «1403/05/01» یا «2024-08-22» یا «14030501» → تاریخِ میلادی (خروجیِ dt.date).
    جداکننده‌ها: /  -  .  و ارقامِ فارسی هم قبوله (۱۴۰۳/۰۵/۰۱).
    • None     یعنی اصلاً شبیهِ تاریخ نیست (مثلاً شماره‌ی پیامه)
    • ValueError یعنی شبیهِ تاریخه ولی نامعتبره (مثلاً 1403/13/45)
    """
    s = to_ascii_digits((raw or "").strip())
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return _make_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if re.fullmatch(r"\d{8}", s):
        try:
            return _make_date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None  # به‌عنوانِ تاریخ درنیومد → پس شماره‌ی پیامه (مثلاً 12345678)
    return None


def parse_time_arg(raw: str) -> tuple[int, int, int] | None:
    """«10:30» / «9:05» / «10:30:15» → (ساعت, دقیقه, ثانیه)؛ اگه ساعت نبود None."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", to_ascii_digits((raw or "").strip()))
    if not m:
        return None
    h, mi, se = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if h > 23 or mi > 59 or se > 59:
        raise ValueError(f"ساعتِ نامعتبره: {raw}")
    return h, mi, se


def parse_start_args(
    tokens: list[str], *, now: dt.datetime | None = None
) -> tuple[str, str, int, dt.datetime | None, bool, list[tuple[str, bool]]]:
    """
    ['@src', '@dst', 'از', '1403/05/01'] → (src_raw, dst_raw, from_id, from_date, drop_author, marks)

    «از …» دو جور قبول می‌کنیم:
      • شماره‌ی پیام: «از 1200» → from_id=1199 (min_id انحصاریه؛ خودِ ۱۲۰۰ هم کپی می‌شه)
      • تاریخ: «از 1403/05/01»، «از 2024-08-22»، «از 14030501»، «از امروز»،
        «از 10:30» (امروز از ساعت ۱۰:۳۰) + ساعتِ اختیاریِ بعدِ تاریخ
        («از 1403/05/01 ساعت 10:30»)
        → from_date: datetimeِ «بدونِ tz» به وقتِ کاربر؛ تبدیلِ به UTC با
          TIMEZONE_OFFSET به عهده‌ی صداکننده‌ست.

    marks: فهرستِ همه‌ی «از …»ها به ترتیبِ ˈ('date', True) | ('id', False)ˈ —
    وقتی «از تاریخ» و «از شماره» هر دو داده شده باشن، کپیِ یک کانال هم‌زمان از
    تاریخ و از شماره شروع می‌شه (هر کدوم جدیدتر بود)؛ ربات این رو نشان می‌ده.

    drop_author=True یعنی بدونِ برچسبِ «Forwarded from» (کپیِ تمیز - پیش‌فرض).
    now: مبنا برای «امروز/دیروز» (بدونِ tz، به وقتِ کاربر).
    """
    tokens = [to_ascii_digits(t) for t in tokens]
    if now is None:
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    refs: list[str] = []
    from_id = 0
    from_date: dt.datetime | None = None
    drop_author = True
    marks: list[tuple[str, bool]] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        low = t.lower()
        if low in _FROM_FLAGS:
            if i + 1 >= len(tokens):
                raise ValueError("بعد از «از» باید تاریخ (مثل 1403/05/01) یا شماره‌ی پیام بیاد.")
            val = tokens[i + 1]
            i += 2

            day: dt.date | None = None
            hh = mm = ss = 0
            rel = _RELATIVE_DATES.get(val.lower())
            if rel is not None:
                day = (now + dt.timedelta(days=rel)).date()
            else:
                day = parse_date_arg(val)  # ممکنه ValueError بده (تاریخِ نامعتبر)
                if day is None:
                    t_only = parse_time_arg(val)
                    if t_only is not None:  # «از 10:30» → امروز از ساعتِ ۱۰:۳۰
                        hh, mm, ss = t_only
                        day = now.date()
                    elif val.isdigit():
                        from_id = int(val) - 1  # min_id انحصاریه؛ «از N» یعنی خودِ N هم کپی بشه
                        marks.append(("id", False))
                        continue
                    else:
                        raise ValueError(
                            f"«{val}» نه تاریخِ معتبریه نه شماره‌ی پیام. "
                            "مثال: از 1403/05/01 | از 2024-08-22 | از 1200 | از امروز"
                        )
            # ساعتِ اختیاری بعدِ تاریخ: «10:30» یا «ساعت 10:30»
            if i < len(tokens) and tokens[i].lower() in _TIME_KEYWORDS:
                i += 1
            if i < len(tokens):
                t_only = parse_time_arg(tokens[i])
                if t_only is not None:
                    hh, mm, ss = t_only
                    i += 1
            cand = dt.datetime(day.year, day.month, day.day, hh, mm, ss)
            from_date = cand if from_date is None else max(from_date, cand)
            marks.append(("date", True))
            continue
        if low in _WITH_AUTHOR_FLAGS:
            drop_author = False
            i += 1
            continue
        refs.append(t)
        i += 1
    if len(refs) != 2:
        raise ValueError("باید دقیقاً دو آدرس بدی: مبدأ و مقصد")
    # شماتیکِ «آدرس/شماره‌ی پیام»: اگر آدرسِ مبدأ اینو داشته باشه، شماره ش شروع می‌شه
    refs[0], embedded = split_ref(refs[0])
    if embedded:
        from_id = max(from_id, embedded - 1)
        marks.append(("id", False))
    return refs[0], refs[1], max(from_id, 0), from_date, drop_author, marks


def start_variants(tokens: list[str], *, now: dt.datetime | None = None) -> list[list[str]]:
    """
    راه‌های ممکنِ جدا‌کردنِ مبدأ/مقصد وقتی اسمِ کانال فاصله داره
    («اخبار مهم» → دو تیکه). هر کاندید رو با parse_start_args امتحان می‌کنیم و
    فقط اونایی که درست پارس می‌شن رو برمی‌گردونیم، به ترتیبِ کم‌ترین چسباندن:
      ۱) بدونِ چسباندن  ۲) فقط یک طرف چسبیده  ۳) هر دو طرف چسبیده
    توکن‌های خودمون (از / بانام / ساعت / …) توی گروهِ سوم می‌مونن.
    """
    tokens = [to_ascii_digits(t) for t in tokens]
    if len(tokens) < 2:
        return []
    cands: list[tuple[int, list[str]]] = []
    seen: set[tuple[str, ...]] = set()
    n = len(tokens)
    for a in range(1, n):
        for b in range(a, n + 1):
            head = " ".join(tokens[:a]).strip()
            mid = " ".join(tokens[a:b]).strip()
            tail = tokens[b:]
            if not head or not mid:
                continue
            cand = [head, mid] + list(tail)
            key = tuple(cand)
            if key in seen:
                continue
            try:
                parse_start_args(list(cand), now=now)
            except ValueError:
                continue
            seen.add(key)
            cands.append(((a - 1) + (b - a - 1), cand))
    cands.sort(key=lambda x: x[0])
    return [c for _, c in cands]


def _split_modifiers(tokens: list[str]) -> tuple[list[str], list[str]]:
    """
    توکن‌ها را به (آدرس‌ها, تعدیل‌کننده‌ها) تقسیم می‌کند.
    تعدیل‌کننده = «از …» (+ مقدار و ساعتِ اختیاری) و «بانام» — با حفظِ ترتیب.
    """
    toks = [to_ascii_digits(t) for t in tokens]
    refs: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(toks):
        low = toks[i].lower()
        if low in _FROM_FLAGS:
            chunk = toks[i:i + 2]
            i += 2
            if i < len(toks) and toks[i].lower() in _TIME_KEYWORDS:
                chunk.append(toks[i])
                i += 1
            if i < len(toks):
                try:
                    is_time = parse_time_arg(toks[i]) is not None
                except ValueError:
                    is_time = False
                if is_time:
                    chunk.append(toks[i])
                    i += 1
            rest.extend(chunk)
            continue
        if low in _WITH_AUTHOR_FLAGS:
            rest.append(toks[i])
            i += 1
            continue
        refs.append(toks[i])
        i += 1
    return refs, rest


def parse_start_any(
    tokens: list[str], *, now: dt.datetime | None = None
) -> tuple[str, str, int, dt.datetime | None, bool, list[tuple[str, bool]], bool]:
    """
    دستورِ شروع را در هر دو شکلِ پشتیبانی‌شده می‌خواند:
      • دو آدرس:  ['@مبدا', '@مقصد', 'از', '1403/05/01']
      • یک آدرس + ریپلای:  ['@مقصد', 'از', '1403/05/01']  ← آدرسِ داده‌شده «مقصد» است و
        مبدأ از پستِ ریپلای‌شده گرفته می‌شود.

    خروجی: (src_raw, dst_raw, from_id, from_date, drop_author, marks, from_reply)
      from_reply=True یعنی src_raw خالی است و صداکننده باید مبدأ را از ریپلای بردارد.
    """
    first_err: ValueError | None = None
    try:
        s, d, fid, fd, da, marks = parse_start_args(list(tokens), now=now)
        return s, d, fid, fd, da, marks, False
    except ValueError as e:
        first_err = e

    refs, rest = _split_modifiers(list(tokens))
    if len(refs) == 1:
        # فقط یک آدرس داده شده → همان مقصد است؛ مبدأ از ریپلای
        _s, _d, fid, fd, da, marks = parse_start_args(["__src__", refs[0]] + rest, now=now)
        return "", refs[0], fid, fd, da, marks, True
    if len(refs) == 0:
        raise ValueError(
            "آدرسی ندادی. یا آدرسِ مقصد را بده و روی پستِ کانالِ مبدأ ریپلای کن "
            "(`.کپی‌کانال شروع @مقصد`)، یا هر دو آدرس را بده."
        )
    raise first_err


# ---------------------------------------------------------- batching ---
@dataclass
class Batch:
    ids: list[int] = field(default_factory=list)   # شناسه‌ی پیام‌های قابلِ فوروارد
    skipped: int = 0                               # پیام‌های سرویسی/ردشده در این دسته
    max_id: int = 0                                # بزرگ‌ترین شناسه‌ی پردازش‌شده


def _is_service(m: Any) -> bool:
    return bool(getattr(m, "action", None)) or m.__class__.__name__ == "MessageService"


async def iter_batches(messages: AsyncIterator[Any], batch_size: int) -> AsyncIterator[Batch]:
    """
    پیام‌ها (صعودی بر اساسِ id) → دسته‌هایی با حداکثر batch_size پیام.
    • پیام‌های سرویسی (عضو شد/پین/…) فوروارد نمی‌شن؛ فقط شمرده می‌شن.
    • پیام‌های هم‌آلبوم (grouped_id یکسان و پشتِ‌سرهم) همیشه توی یک دسته می‌مونن.
    • max_id هر دسته فقط شاملِ پیام‌های «کاملاً» داخلِ همون دسته‌ست؛ پس ادامه از
      روی last_id هیچ پیام/آلبومی رو جا نمی‌ندازه.
    """
    batch_size = max(1, min(batch_size, TELEGRAM_MAX_FORWARD_BATCH))
    cur = Batch()
    ready: list[Batch] = []
    album: list[Any] = []
    album_gid: Any = None

    def add_unit(unit: list[Any]) -> None:
        nonlocal cur
        if cur.ids and len(cur.ids) + len(unit) > batch_size:
            ready.append(cur)
            cur = Batch()
        for u in unit:
            cur.ids.append(u.id)
            cur.max_id = max(cur.max_id, u.id)
        if len(cur.ids) >= batch_size:
            ready.append(cur)
            cur = Batch()

    def close_album() -> None:
        nonlocal album, album_gid
        if album:
            add_unit(album)
            album, album_gid = [], None

    async for m in messages:
        if _is_service(m):
            close_album()  # آلبومِ در انتظار قبل از شمارشِ این پیام بسته می‌شه (ترتیبِ max_id حفظ بشه)
            cur.skipped += 1
            cur.max_id = max(cur.max_id, m.id)
        else:
            gid = getattr(m, "grouped_id", None)
            if gid is not None and album and gid == album_gid:
                album.append(m)
            else:
                close_album()
                if gid is not None:
                    album, album_gid = [m], gid
                else:
                    add_unit([m])
        for b in ready:
            yield b
        ready.clear()

    close_album()
    for b in ready:
        yield b
    if cur.ids or cur.skipped:
        yield cur


# --------------------------------------------------- پیدا کردنِ تاریخ ---
_PROBE_RADIUS = 32      # شعاعِ اولیه‌ی گشتنِ اطرافِ یک شناسه
_PROBE_RADIUS_MAX = 160  # حداکثرِ شعاعِ اگه اول چیزی پیدا نشد
_ID_CHUNK = 99          # حداکثرِ شناسه در هر fetch (تلگرام سقفِ ۱۰۰ داره)


def _as_utc(d: dt.datetime) -> dt.datetime:
    if d.tzinfo is None:
        return d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


async def _probe(fetch, idx: int, low: int, high: int) -> tuple[int, dt.datetime] | None:
    """نزدیک‌ترین پیامِ *موجود* به شناسه‌ی idx داخلِ بازه‌ی [low, high] + تاریخش."""
    r = _PROBE_RADIUS
    while True:
        a, b = max(low, idx - r), min(high, idx + r)
        found = await fetch(list(range(a, b + 1)))
        if found:
            near = min(found, key=lambda i: (abs(i - idx), i))
            return near, _as_utc(found[near])
        if r >= _PROBE_RADIUS_MAX:
            return None
        r *= 5


async def _probe_from_top(fetch, low: int, high: int) -> tuple[int, dt.datetime] | None:
    """نزدیک‌ترین پیامِ موجود به «بالایِ بازه» — اگه اطرافش حذف شده بود، تکه‌تکه به پایین."""
    hi = await _probe(fetch, high, low, high)
    if hi is not None:
        return hi
    cur = high
    for _ in range(20):  # حداکثرِ ~۲۰۰۰ شناسه پایین‌تر، فقط برایِ حالتِ خیلی عجیب
        start = max(low, cur - _ID_CHUNK + 1)
        got = await fetch(list(range(start, cur + 1)))
        if got:
            near = max(got)
            return near, _as_utc(got[near])
        if start <= low:
            break
        cur = start - 1
    return None


async def _expand_around(fetch, mid: int, low: int, high: int, max_ids: int = 1980):
    """
    بازه‌ی «کاملِ پوشش‌داده‌شده»‌ی [a, b] دورِ mid که حداقل یک پیامِ موجود توش هست
    (یا اگه تا بودجه هیچی نبود، همون بازه‌ی بزرگ‌شده‌ی خالی). خروجی: (found, a, b)
    """
    a = max(low + 1, mid - _ID_CHUNK // 2)
    b = min(high - 1, mid + _ID_CHUNK // 2)
    found: dict[int, dt.datetime] = {}
    spent = 0
    while spent < max_ids:
        na = max(low + 1, a - _ID_CHUNK)
        nb = min(high - 1, b + _ID_CHUNK)
        if na == a and nb == b:
            break
        for ids in (list(range(na, a)), list(range(b + 1, nb + 1))):
            if not ids:
                continue
            got = await fetch(ids)
            found.update(got)
            spent += len(ids)
        a, b = na, nb
        if found:
            break
    return found, a, b


async def find_start_id(fetch, low: int, high: int, target: dt.datetime) -> int | None:
    """
    اولین شناسه‌ی پیامی که تاریخش >= target است (جستجوی دودویی رویِ شناسه‌ها).

    fetch: کال‌بکِ async با امضای `fetch(ids: list[int]) -> dict[int, dt.datetime]`
           که فقط پیام‌های موجود رو برمی‌گردونه (پیامِ حذف‌شده اصلاً توش نیست).
    خروجی: شناسه‌ی شروع — صداکننده باید `last_id = خروجی - 1` بذاره
           (چون iter_messages با min_id انحصاریه) — یا None اگه از این تاریخ
           پیامی توی کانال نباشه.

    تقریباً ~log2(بازه) درخواست (۲۰-۲۵ تا برای کانالِ میلیونی)؛ هر درخواست
    حداکثرِ ۹۹ شناسه. اگه پیام‌هایِ اطرافِ یک شناسه حذف‌شده باشن، دورش رو
    (حداکثرِ ~۲۰۰۰ شناسه) می‌گردیم تا مرز دقیق پیدا بشه.

    قاعده‌ی ایمنی: هر جا ابهام باشه (پیامِ حذف‌شده و ...) مرز رو طوری جلو
    می‌بریم که ***هیچ پیامِ تازه‌ای جا نمونه***؛ برعکسش ممکنه چند پیامِ
    قدیمی‌ترِ اضافه کپی بشه (فقط توی کانالِ پُر از پیامِ حذف‌شده).
    """
    target = _as_utc(target)
    if high <= low:
        return None

    hi = await _probe_from_top(fetch, low, high)
    if hi is None or hi[1] < target:
        return None  # آخرین پیام هم از تاریخِ خواسته‌شده قدیمی‌تره (یا کانال خالیه)

    lo = await _probe(fetch, low, low, high)
    if lo is not None and lo[1] >= target:
        return lo[0]  # خودِ ابتدایِ کانال هم از این تاریخ به بعدِ

    # L: بالایِ بازه‌ی جستجو که «قطعاً» بالاتر از اون نیست (F > L) • U: تازه (F <= U)
    L = lo[0] if lo is not None else low
    U = hi[0]
    while U - L > 1:
        mid = (L + U) // 2
        a = max(L + 1, mid - _ID_CHUNK // 2)
        b = min(U - 1, mid + _ID_CHUNK // 2)
        found = await fetch(list(range(a, b + 1)))
        for attempt in range(2):
            news = sorted(i for i, d in found.items() if _as_utc(d) >= target)
            olds = sorted(i for i, d in found.items() if _as_utc(d) < target)
            if news:
                U = news[0]  # اولین پیامِ تازه‌ی دیده‌شده (همیشه < U چون بازه clip شده)
                if olds:
                    L = max(L, olds[-1])
                break
            if olds and olds[-1] > L:
                L = olds[-1]  # اینا قطعاً قدیمی‌ان؛ تازه‌ها بالاترن
                break
            if a <= L + 1:
                # بازه از درستِ بالایِ L شروع شده، کامل دیده شده و تازه‌ای توش نبود
                L = b
                break
            if attempt == 0:
                # کلِ بازه حذف‌شده‌ست → دورِ mid رو گسترش بده تا پیامی پیدا بشه
                found, a, b = await _expand_around(fetch, mid, L, U)
                continue
            # بودجه‌ی گسترش تموم شد → محافظه‌کارانه مرزِ بالا رو عقب می‌بریم
            # (ممکنه چند پیامِ قدیمی‌ترِ اضافه کپی بشه؛ پیامِ تازه جا نمی‌مونه)
            U = a
    return U


# ------------------------------------------------- private chat links ---
UID_OFFSET = 4_000_000_000   # ارجاعِ ساختگی برای پوشه‌ها (جدا از شناسه‌های واقعیِ چت)
FOLDER_MAX = 255             # تلگرام برای پوشه‌ها فقط ۰..۲۵۵ می‌پذیره

_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t|telegram)\.me/([A-Za-z0-9_+\-/]+)", re.IGNORECASE
)


def _classify_link(tail: str) -> dict | None:
    """«+hash» / «joinchat/hash» / «c/123/45» / «user/45» → دیکشنریِ لینک یا None."""
    tail = tail.strip("/")
    if not tail:
        return None
    m = re.fullmatch(r"\+([A-Za-z0-9_-]+)", tail)
    if m:
        return {"kind": "invite", "hash": m.group(1), "ref": f"https://t.me/+{m.group(1)}",
                "message_id": 0, "name": ""}
    m = re.fullmatch(r"joinchat/([A-Za-z0-9_-]+)", tail, re.IGNORECASE)
    if m:
        return {"kind": "invite", "hash": m.group(1), "ref": f"https://t.me/joinchat/{m.group(1)}",
                "message_id": 0, "name": ""}
    m = re.fullmatch(r"c/(\d+)(?:/(\d+))?", tail)
    if m:
        return {"kind": "private", "hash": "", "ref": f"t.me/c/{m.group(1)}",
                "message_id": int(m.group(2) or 0), "name": ""}
    m = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]{3,31})(?:/(\d+))?", tail)
    if m:
        return {"kind": "public", "hash": "", "ref": f"@{m.group(1)}",
                "message_id": int(m.group(2) or 0), "name": ""}
    return None


def extract_protected_links(text: str | None, entities: list | None = None) -> list[dict]:
    """
    لینک‌های کانال/گروهی که توی متنِ یک پیام هستن → فهرستِ لینک‌ها.

    سه جور لینک تشخیص داده می‌شه:
      • «private»  → t.me/c/<شناسه>/<شماره>  (کانالِ خصوصی؛ برایِ پیدا کردنِ خودِ کانال)
      • «invite»   → t.me/+hash و t.me/joinchat/hash  (لینکِ دعوتِ خصوصی)
      • «public»   → t.me/<یوزرنیم>/<شماره>

    لینک‌های «متنِ دلخواه → آدرس» (MessageEntityTextUrl) هم خونده می‌شن، چون
    خیلی از کانال‌ها اسمِ کانالِ بعدی رو به‌صورتِ لینک می‌ذارن.

    خروجی: [{"kind", "hash", "ref", "message_id", "name"}]
      ref  → قابلِ دادنِ مستقیم به parse_chat_ref (برایِ invite با joinchat سرچ می‌شه)
      name → متنِ قابلِ نمایشِ لینک (وقتی لینک رویِ یک اسم نشسته باشه)
    """
    text = text or ""
    found: list[dict] = []
    seen: set[tuple[str, str, int]] = set()

    def push(item: dict | None, name: str = "") -> None:
        if not item:
            return
        item["name"] = name
        key = (item["kind"], item["hash"] or item["ref"], item["message_id"])
        if key in seen:
            return
        seen.add(key)
        found.append(item)

    name_by_url: dict[str, str] = {}
    for ent in entities or []:
        cls = ent.__class__.__name__
        url = getattr(ent, "url", None)
        if cls in ("MessageEntityTextUrl", "MessageEntityUrl") and url:
            name_by_url[url] = text[ent.offset:ent.offset + ent.length]
        elif cls == "MessageEntityUrl":
            name_by_url[text[ent.offset:ent.offset + ent.length]] = ""
    for ent in entities or []:
        url = getattr(ent, "url", None) or ""
        if not url:
            continue
        m = _LINK_RE.search(url)
        if m:
            push(_classify_link(m.group(1)), text[ent.offset:ent.offset + ent.length])

    for m in _LINK_RE.finditer(text):
        label = name_by_url.get(m.group(0), "")
        push(_classify_link(m.group(1)), label)
    return found


def ref_label(ref: str) -> str:
    """برچسبِ کوتاهِ یک ارجاع (پوشه/آیدی/یوزرنیم) برای پیام‌های ربات."""
    s = (ref or "").strip()
    if s.startswith("folder:"):
        n = s.split(":", 1)[1]
        return f"پوشه‌ی شماره {n}" if n != "0" else "چت‌های اصلی (بدونِ پوشه)"
    return s


# ------------------------------------------------------ error classes ---
_WAIT_ERRORS = {"FloodWaitError", "SlowModeWaitError", "FloodPremiumWaitError"}

_FATAL_ERRORS = {
    "ChatForwardsRestrictedError": "فورواردِ این کانال/چت توسطِ مالکش بسته شده (محتوای محافظت‌شده)؛ کپی ممکن نیست.",
    "ChatWriteForbiddenError": "اجازه‌ی ارسال توی کانالِ مقصد رو نداری.",
    "ChatAdminRequiredError": "برای ارسال توی مقصد باید ادمین (با دسترسیِ انتشارِ پست) باشی.",
    "ChatRestrictedError": "ارسال توی مقصد برات محدود شده.",
    "UserBannedInChannelError": "توی یکی از کانال‌ها بن/محدود شدی.",
    "ChannelPrivateError": "دسترسی به یکی از کانال‌ها رو از دست دادی (خصوصی شده یا اخراج شدی).",
    "ChannelInvalidError": "یکی از کانال‌ها نامعتبره/حذف شده.",
    "ChannelBannedError": "یکی از کانال‌ها توسطِ تلگرام مسدود شده.",
    "ChatIdInvalidError": "شناسه‌ی چت نامعتبره.",
    "PeerFloodError": "تلگرام اکانت رو موقتاً به‌خاطرِ تعدادِ زیادِ درخواست محدود کرده (PeerFlood). چند ساعت صبر کن و بعد «ادامه» بزن.",
    "AuthKeyUnregisteredError": "سشن باطل شده.",
    "UserDeactivatedError": "اکانت غیرفعال شده.",
    "UserDeactivatedBanError": "اکانت مسدود شده.",
}

_SKIP_ERRORS = {"MessageIdInvalidError", "MessageEmptyError", "MediaEmptyError", "MessageNotModifiedError"}

_FATAL_BY_MESSAGE = (
    ("CHAT_FORWARDS_RESTRICTED", "ChatForwardsRestrictedError"),
    ("CHAT_WRITE_FORBIDDEN", "ChatWriteForbiddenError"),
    ("CHAT_ADMIN_REQUIRED", "ChatAdminRequiredError"),
    ("PEER_FLOOD", "PeerFloodError"),
    ("USER_BANNED_IN_CHANNEL", "UserBannedInChannelError"),
)


def classify_error(exc: BaseException) -> tuple[str, Any]:
    """
    ('wait', ثانیه) | ('fatal', پیامِ فارسی) | ('skip', None) | ('retry', None)
    بر اساسِ «نامِ کلاس» (و در صورتِ نبودِ کلاسِ اختصاصی در نسخه‌ی Telethon، متنِ RPC)
    تا به نسخه‌ی خاصی از Telethon وابسته نباشیم.
    """
    name = exc.__class__.__name__
    if name in _WAIT_ERRORS:
        secs = getattr(exc, "seconds", None)
        try:
            secs = int(secs)
        except (TypeError, ValueError):
            secs = 30
        return "wait", max(secs, 1)
    if name in _FATAL_ERRORS:
        return "fatal", _FATAL_ERRORS[name]
    if name in _SKIP_ERRORS:
        return "skip", None
    text = str(exc).upper()
    for needle, key in _FATAL_BY_MESSAGE:
        if needle in text:
            return "fatal", _FATAL_ERRORS[key]
    if "FLOOD_WAIT" in text:
        m = re.search(r"(\d+)", text)
        return "wait", int(m.group(1)) if m else 30
    return "retry", None


# ------------------------------------------------------- daily window ---
def check_window(
    now: dt.datetime,
    window_start: dt.datetime | None,
    window_count: int,
    limit: int,
    n: int,
) -> tuple[float, dt.datetime | None, int]:
    """
    سقفِ روزانه (پنجره‌ی ۲۴ساعته از اولین ارسال).
    خروجی: (ثانیه‌ی انتظار — ۰ یعنی مجازه, window_start, window_count) بعد از ریستِ احتمالی.
    فراخواننده بعد از ارسالِ موفق، window_count رو با تعدادِ واقعیِ کپی‌شده زیاد می‌کنه.
    """
    if limit <= 0:
        return 0.0, window_start, window_count
    if window_start is None or now - window_start >= DAY:
        return 0.0, now, 0
    if window_count > 0 and window_count + n > limit:
        wait = (window_start + DAY - now).total_seconds()
        return max(wait, 1.0), window_start, window_count
    return 0.0, window_start, window_count


# ----------------------------------------------------------- display ---
STATUS_LABELS = {
    "running": "در حال اجرا ▶️",
    "paused": "متوقف ⏸",
    "done": "تمام‌شده ✅",
    "watching": "از این به بعد خودکار 👀",
    "error": "خطا ❌",
}


def _fmt_duration(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} ساعت و {m} دقیقه"
    if m:
        return f"{m} دقیقه"
    return f"{s} ثانیه"


def format_from_date(fd: dt.datetime) -> str:
    """
    تاریخِ شروعِ خواسته‌شده (بدونِ tz، به وقتِ کاربر) →
    «1403/05/01 (2024/08/22)» یا با ساعت: «1403/05/01 (2024/08/22) ساعت 10:30»
    """
    if fd.tzinfo is not None:
        fd = fd.replace(tzinfo=None)
    jy, jm, jd = gregorian_to_jalali(fd.year, fd.month, fd.day)
    out = f"{jy:04d}/{jm:02d}/{jd:02d} ({fd.year:04d}/{fd.month:02d}/{fd.day:02d})"
    if (fd.hour, fd.minute, fd.second) != (0, 0, 0):
        t = f"{fd.hour:02d}:{fd.minute:02d}"
        if fd.second:
            t += f":{fd.second:02d}"
        out += f" ساعت {t}"
    return out


def format_status(job: dict, live: dict | None = None) -> str:
    live = live or {}
    copied, skipped, total = job["copied"], job["skipped"], job.get("total_hint", 0)
    lines = [
        f"📦 **کپی کانال #{job['id']}**",
        f"• مبدأ: {job['source_title'] or job['source_id']}",
        f"• مقصد: {job['dest_title'] or job['dest_id']}",
        f"• وضعیت: {STATUS_LABELS.get(job['status'], job['status'])}",
    ]
    if job.get("from_date"):
        lines.append(f"• شروع از تاریخ: {format_from_date(job['from_date'])}")
    if job.get("watch"):
        lines.append("• حالتِ «از این به بعد»: پیام‌های تازه هم خودکار کپی می‌شن 👀")
    if job.get("children"):
        kids = len([x for x in str(job["children"]).split(",") if x.strip().isdigit()])
        lines.append(f"• چند کانال با هم ({kids} کانالِ مبدأ)")
    if total > 0:
        pct = min(int((copied + skipped) * 100 / total), 100)
        lines.append(f"• پیشرفت: {copied} کپی‌شده از حدودِ {total} ({pct}%)")
    else:
        lines.append(f"• کپی‌شده: {copied}")
    if skipped:
        lines.append(f"• ردشده: {skipped} (پیامِ سرویسی/حذف‌شده)")
    lines.append(f"• آخرین پیامِ پردازش‌شده: #{job['last_id']}")
    lines.append("• حالت: " + ("با نامِ مبدأ" if not job.get("drop_author", True) else "بدونِ برچسبِ فوروارد"))

    if job["status"] == "running":
        if live.get("state"):
            lines.append(f"• الان: {live['state']}")
        t0, c0 = live.get("t0"), live.get("copied0", 0)
        now = live.get("now")
        if t0 is not None and now is not None and copied > c0 and total > 0:
            rate = (copied - c0) / max(now - t0, 1)
            remaining = max(total - copied - skipped, 0)
            if rate > 0 and remaining:
                lines.append(f"• زمانِ باقی‌مانده (تقریبی): {_fmt_duration(remaining / rate)}")
    if job.get("last_error"):
        lines.append(f"• ⚠️ {job['last_error']}")
    return "\n".join(lines)
