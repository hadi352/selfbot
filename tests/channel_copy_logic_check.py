"""تستِ منطقِ خالصِ کپی کانال (بدونِ Telethon/DB): پارس، دسته‌بندی با آلبوم، خطاها، سقفِ روزانه."""
import asyncio
import datetime as dt
import importlib.util
import os
import sys
from types import SimpleNamespace as NS

# بدونِ import کردنِ bot/__init__ (که config/telethon می‌خواد) ماژولِ خالص رو لود می‌کنیم
_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot", "channel_copy_core.py")
_spec = importlib.util.spec_from_file_location("channel_copy_core", _p)
core = importlib.util.module_from_spec(_spec)
sys.modules["channel_copy_core"] = core
_spec.loader.exec_module(core)


def msg(i, gid=None, service=False):
    return NS(id=i, grouped_id=gid, action=("x" if service else None))


async def agen(items):
    for it in items:
        yield it


def batches(items, size):
    async def run():
        return [b async for b in core.iter_batches(agen(items), size)]
    return asyncio.run(run())


def test_parse_chat_ref():
    assert core.parse_chat_ref("@durov") == ("username", "durov")
    assert core.parse_chat_ref("https://t.me/durov/123") == ("username", "durov")
    assert core.parse_chat_ref("t.me/c/1234567/89") == ("id", -1001234567)
    assert core.parse_chat_ref("-1001234567") == ("id", -1001234567)
    assert core.parse_chat_ref("1234567") == ("id", 1234567)
    for bad in ("", "a", "https://t.me/+AbCdEf", "t.me/joinchat/xyz", "no way!"):
        try:
            core.parse_chat_ref(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_parse_start_args():
    now = dt.datetime(2026, 10, 15, 12, 0)

    def p(toks):
        return core.parse_start_args(list(toks), now=now)

    assert p(["@a", "@b"]) == ("@a", "@b", 0, None, True, [])
    assert p(["@a", "@b", "از", "100"]) == ("@a", "@b", 99, None, True, [("id", False)])
    assert p(["@a", "@b", "با‌نام"]) == ("@a", "@b", 0, None, False, [])
    assert p(["@a", "@b", "بانام", "from", "5"]) == ("@a", "@b", 4, None, False, [("id", False)])
    # شروع با تاریخ (بدونِ tz = به وقتِ کاربر)
    assert p(["@a", "@b", "از", "1403/05/01"]) == (
        "@a", "@b", 0, dt.datetime(2024, 7, 22), True, [("date", True)]
    )
    assert p(["@a", "@b", "از", "2024-08-22"]) == (
        "@a", "@b", 0, dt.datetime(2024, 8, 22), True, [("date", True)]
    )
    assert p(["@a", "@b", "از", "۱۴۰۳/۰۵/۰۱"])[3] == dt.datetime(2024, 7, 22)
    assert p(["@a", "@b", "از", "14030501"])[3] == dt.datetime(2024, 7, 22)
    assert p(["@a", "@b", "از", "1403/05/01", "10:30"])[3] == dt.datetime(2024, 7, 22, 10, 30)
    assert p(["@a", "@b", "از", "1403/05/01", "ساعت", "9:05"])[3] == dt.datetime(2024, 7, 22, 9, 5)
    assert p(["@a", "@b", "از", "امروز"])[3] == dt.datetime(2026, 10, 15)
    assert p(["@a", "@b", "از", "دیروز", "18:00"])[3] == dt.datetime(2026, 10, 14, 18, 0)
    assert p(["@a", "@b", "از", "10:30"])[3] == dt.datetime(2026, 10, 15, 10, 30)
    # شماره‌ی پیامِ ۸ رقمی که تاریخِ معتبری نیست، همون شماره‌ی پیام می‌مونه
    assert p(["@a", "@b", "از", "12345678"]) == ("@a", "@b", 12345677, None, True, [("id", False)])
    # «آدرس/شماره‌ی پیام»: اولِ کپی از همون شماره
    assert p(["@src/500", "@dst"]) == ("@src", "@dst", 499, None, True, [("id", False)])
    assert p(["t.me/durov/42", "@dst"]) == ("t.me/durov", "@dst", 41, None, True, [("id", False)])
    # «از تاریخ» و «از شماره» با هم ← هر کدوم جدیدتر باشه ملاکه (marks گزارش می‌ده)
    assert p(["@a", "@b", "از", "1403/05/01", "از", "900"]) == (
        "@a", "@b", 899, dt.datetime(2024, 7, 22), True, [("date", True), ("id", False)]
    )
    assert p(["@a", "@b", "از", "900", "از", "1403/05/01"])[5] == [("id", False), ("date", True)]
    for bad in (
        ["@a"],
        ["@a", "@b", "@c"],
        ["@a", "@b", "از"],
        ["@a", "@b", "از", "x"],
        ["@a", "@b", "از", "1403/13/45"],          # تاریخِ نامعتبر
        ["@a", "@b", "از", "2024-13-01"],           # ماهِ نامعتبر
        ["@a", "@b", "از", "25:00"],                # ساعتِ نامعتبر
    ):
        try:
            p(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_parse_start_any():
    now = dt.datetime(2026, 10, 15, 12, 0)
    # دو آدرس (مثلِ قبل)
    assert core.parse_start_any(["@src", "@dst"], now=now) == (
        "@src", "@dst", 0, None, True, [], False
    )
    # یک آدرس + ریپلای: همان آدرس مقصد است و مبدأ از ریپلای می‌آید
    assert core.parse_start_any(["@gs6378g"], now=now) == (
        "", "@gs6378g", 0, None, True, [], True
    )
    assert core.parse_start_any(["@dst", "از", "1403/05/01"], now=now) == (
        "", "@dst", 0, dt.datetime(2024, 7, 22), True, [("date", True)], True
    )
    assert core.parse_start_any(["@dst", "از", "1403/05/01", "ساعت", "10:30"], now=now)[3] == dt.datetime(
        2024, 7, 22, 10, 30
    )
    assert core.parse_start_any(["@dst", "از", "500"], now=now)[2] == 499
    # «ازاینبعد» قبل از پارس توسطِ هندلر جدا می‌شود (توکنِ watch)؛ اینجا حالتِ جدا‌شده:
    assert core.parse_start_any(["@dst"], now=now)[6] is True
    assert core.parse_start_any(["@dst", "با‌نام"], now=now) == (
        "", "@dst", 0, None, False, [], True
    )
    # خرابی‌ها
    for bad in ([], ["@a", "@b", "@c"], ["@dst", "از"], ["@dst", "از", "x"]):
        try:
            core.parse_start_any(bad, now=now)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_split_ref_and_labels():
    assert core.split_ref("@ch/12345") == ("@ch", 12345)
    assert core.split_ref("t.me/ch/9") == ("t.me/ch", 9)
    assert core.split_ref("۱۴۰۳/۱۲") == ("1403", 12)  # ارقامِ فارسی هم اول به لاتین تبدیل می‌شن
    # لینکِ کانالِ خصوصی: شناسه‌ی کانال دست‌نخورده، شماره‌ی پیامِ آخر جدا می‌شه
    assert core.split_ref("t.me/c/1234567890") == ("t.me/c/1234567890", 0)
    assert core.split_ref("t.me/c/1234567890/55") == ("t.me/c/1234567890", 55)
    assert core.split_ref("@ch") == ("@ch", 0)
    assert core.split_ref("https://t.me/c/1234567890/55") == ("https://t.me/c/1234567890", 55)
    assert core.ref_label("folder:3") == "پوشه‌ی شماره 3"
    assert core.ref_label("folder:0") == "چت‌های اصلی (بدونِ پوشه)"
    assert core.ref_label("@ch") == "@ch"


def test_extract_protected_links():
    txt = ("سلام بچه‌ها، کانال جدیدمون: https://t.me/+AbCdEf123 و "
           "پستِ خاص: t.me/c/1234567890/55 و کانالِ اصلی t.me/durov/7 نگاه کنید")
    got = core.extract_protected_links(txt)
    kinds = [g["kind"] for g in got]
    assert kinds == ["invite", "private", "public"], got
    assert got[0]["hash"] == "AbCdEf123"
    assert got[0]["ref"] == "https://t.me/+AbCdEf123"
    assert got[1]["message_id"] == 55 and got[1]["ref"] == "t.me/c/1234567890"
    assert got[2]["ref"] == "@durov" and got[2]["message_id"] == 7
    # joinchat، بدونِ اسکیم، و تکراری‌ها
    got = core.extract_protected_links("t.me/joinchat/Xy-Z_1 و t.me/joinchat/Xy-Z_1")
    assert len(got) == 1 and got[0]["kind"] == "invite" and got[0]["hash"] == "Xy-Z_1"
    assert core.extract_protected_links("متنِ ساده بدونِ لینک") == []
    assert core.extract_protected_links(None) == []
    # لینکی که اسکیم نداره و یوزرنیمِ کوتاه/نامعتبره نباید کانال حساب بشه
    assert core.extract_protected_links("t.me/+") == []
    assert core.extract_protected_links("www.telegram.me/durov")[0]["ref"] == "@durov"


class _Ent:
    """شبیه‌سازِ Telethon MessageEntity (فقط offset/length/url و نامِ کلاس مهمه)."""

    def __init__(self, offset: int, length: int, url: str = ""):
        self.offset, self.length, self.url = offset, length, url


class _TextUrl(_Ent):
    """مثلِ MessageEntityTextUrl: آدرسِ واقعی جدا از متنِ نمایشی."""


class _Url(_Ent):
    """مثلِ MessageEntityUrl: خودِ متن آدرسه."""


def test_extract_links_from_entities():
    """اسمِ کانال به‌صورتِ لینک: متنِ نمایشی = اسم، آدرس = لینکِ دعوت."""
    txt = "📢 کانالِ ویژه: اینجا کلیک کنید"
    got = core.extract_protected_links(txt, [_TextUrl(15, 15, "https://t.me/+Secret99")])
    assert got and got[0]["kind"] == "invite" and got[0]["hash"] == "Secret99"
    assert got[0]["name"] == txt[15:30]
    # لینکِ t.me/c که به‌صورتِ متنِ معمولی (MessageEntityUrl) اومده
    url = "https://t.me/c/1234567890/55"
    txt2 = f"ببین {url} رو"
    got2 = core.extract_protected_links(txt2, [_Url(5, len(url), url)])
    assert len(got2) == 1 and got2[0]["kind"] == "private" and got2[0]["message_id"] == 55
    # چند لینکِ تکراری (هم entity هم متن) نباید دوبار بیان
    got3 = core.extract_protected_links("t.me/durov/9", [_Ent(0, 13, "t.me/durov/9")])
    assert len(got3) == 1


def test_parse_date_and_time():
    assert core.parse_date_arg("1403/05/01") == dt.date(2024, 7, 22)
    assert core.parse_date_arg("1403-5-1") == dt.date(2024, 7, 22)
    assert core.parse_date_arg("2024-08-22") == dt.date(2024, 8, 22)
    assert core.parse_date_arg("۱۴۰۳/۰۵/۰۱") == dt.date(2024, 7, 22)
    assert core.parse_date_arg("14030501") == dt.date(2024, 7, 22)
    assert core.parse_date_arg("1404/01/01") == dt.date(2025, 3, 21)  # عیدِ ۱۴۰۴
    assert core.parse_date_arg("1403/12/30") == dt.date(2025, 3, 20)  # اسفندِ کبیسه
    # نه-تاریخ → None
    for s in ("1200", "12345678", "abc", "2024", ""):
        assert core.parse_date_arg(s) is None, s
    # شبیهِ تاریخ ولی خراب → ValueError
    for s in ("1403/13/45", "1403/07/31", "1404/12/30", "2024-13-01", "1403/12/31"):
        try:
            core.parse_date_arg(s)
        except ValueError:
            continue
        raise AssertionError(s)
    assert core.parse_time_arg("10:30") == (10, 30, 0)
    assert core.parse_time_arg("9:05") == (9, 5, 0)
    assert core.parse_time_arg("10:30:15") == (10, 30, 15)
    assert core.parse_time_arg("1200") is None
    try:
        core.parse_time_arg("25:00")
    except ValueError:
        pass
    else:
        raise AssertionError("25:00 باید خطا بده")


# ----------------------------------------------------- find_start_id ---
EPOCH = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)


def _dates(n, deleted=()):
    return {i: EPOCH + dt.timedelta(hours=i) for i in range(1, n + 1) if i not in set(deleted)}


def _find(dates, target, low=1, high=None, stats=None):
    async def fetch(ids):
        if stats is not None:
            stats["reqs"] += 1
            stats["max_chunk"] = max(stats["max_chunk"], len(ids))
        return {i: dates[i] for i in ids if i in dates}

    if high is None:
        high = max(dates) if dates else 0
    return asyncio.run(core.find_start_id(fetch, low, high, target))


def _first(dates, target):
    ids = sorted(i for i, d in dates.items() if d >= target)
    return ids[0] if ids else None


def test_find_start_id_basics():
    d = _dates(2000)
    assert _find(d, EPOCH + dt.timedelta(hours=500)) == 500          # دقیقاً رویِ تاریخِ پیام
    assert _find(d, EPOCH + dt.timedelta(hours=500, seconds=30)) == 501  # وسطِ دو پیام
    assert _find(d, EPOCH - dt.timedelta(days=1)) == 1               # قدیمی‌تر از همه
    assert _find(d, EPOCH + dt.timedelta(hours=99999)) is None       # جدیدتر از همه
    assert _find({}, EPOCH) is None                                  # کانالِ خالی
    # پیامِ حذف‌شده دورِ مرز
    dd = _dates(2000, deleted=range(480, 521))
    assert _find(dd, EPOCH + dt.timedelta(hours=500)) == 521


def test_find_start_id_never_skips():
    """هیچ‌وقت نباید پیامِ تازه‌ای جا بمونه — حتی با پیامِ حذف‌شده‌ی زیاد."""
    import random

    random.seed(11)
    for _ in range(150):
        n = random.choice([200, 2000])
        dates = _dates(n)
        for _ in range(random.randint(0, 3)):  # چند بازه‌ی حذف‌شده
            s = random.randint(1, n)
            for i in range(s, min(n, s + random.randint(1, 400)) + 1):
                dates.pop(i, None)
        if not dates:
            continue
        target = EPOCH + dt.timedelta(hours=random.randint(1, n))
        expected = _first(dates, target)
        got = _find(dates, target)
        if expected is None:
            assert got is None, (n, target, got)
        else:
            assert got is not None and got <= expected, (n, target, expected, got)


def test_find_start_id_budget():
    """جستجو باید ارزون باشه: هر درخواست حداکثر ۹۹ شناسه."""
    stats = {"reqs": 0, "max_chunk": 0}
    assert _find(_dates(200000), EPOCH + dt.timedelta(hours=150000), stats=stats) == 150000
    assert stats["max_chunk"] <= 99
    assert stats["reqs"] <= 30, stats


def test_batches_size_and_order():
    out = batches([msg(i) for i in range(1, 46)], 20)
    assert [len(b.ids) for b in out] == [20, 20, 5]
    assert [b.max_id for b in out] == [20, 40, 45]
    assert sum((b.ids for b in out), []) == list(range(1, 46))


def test_album_never_split():
    items = [msg(1), msg(2), msg(3, gid=7), msg(4, gid=7), msg(5, gid=7), msg(6)]
    out = batches(items, 4)
    # آلبوم (۳-۵) نباید نصف بشه: دسته‌ی اول [1,2]، دسته‌ی دوم [3,4,5,6]
    assert [b.ids for b in out] == [[1, 2], [3, 4, 5, 6]]
    out = batches([msg(i, gid=9) for i in range(1, 11)] + [msg(11)], 5)
    assert [len(b.ids) for b in out] == [10, 1]  # آلبومِ ۱۰تایی حتی بزرگ‌تر از batch_size کامل می‌مونه


def test_batch_cap_100():
    out = batches([msg(i) for i in range(1, 251)], 1000)
    assert max(len(b.ids) for b in out) == 100


def test_service_messages():
    out = batches([msg(1), msg(2, service=True), msg(3)], 20)
    assert len(out) == 1 and out[0].ids == [1, 3] and out[0].skipped == 1 and out[0].max_id == 3
    out = batches([msg(1, service=True), msg(2, service=True)], 20)
    assert out[0].ids == [] and out[0].skipped == 2 and out[0].max_id == 2
    # سرویسی بعد از آلبوم نباید max_id رو از آلبومِ ناتمام جلو ببره
    out = batches([msg(1, gid=5), msg(2, gid=5), msg(3, service=True), msg(4)], 2)
    assert [b.ids for b in out] == [[1, 2], [4]]
    assert out[0].max_id == 2 or out[0].max_id == 3  # آلبوم داخلِ دسته‌ست، پس جلو رفتن مشکلی نداره


class FloodWaitError(Exception):
    seconds = 42


class ChatForwardsRestrictedError(Exception):
    pass


class PeerFloodError(Exception):
    pass


class MessageIdInvalidError(Exception):
    pass


def test_classify():
    assert core.classify_error(FloodWaitError()) == ("wait", 42)
    assert core.classify_error(ChatForwardsRestrictedError())[0] == "fatal"
    assert core.classify_error(PeerFloodError())[0] == "fatal"
    assert core.classify_error(MessageIdInvalidError()) == ("skip", None)
    assert core.classify_error(RuntimeError("CHAT_FORWARDS_RESTRICTED"))[0] == "fatal"
    assert core.classify_error(RuntimeError("A wait of 17 seconds is required (FLOOD_WAIT_17)")) == ("wait", 17)
    assert core.classify_error(ValueError("boom")) == ("retry", None)


def test_window():
    now = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
    assert core.check_window(now, None, 0, 100, 20) == (0.0, now, 0)
    assert core.check_window(now, now, 50, 0, 20)[0] == 0.0  # بدونِ سقف
    assert core.check_window(now, now, 50, 100, 20)[0] == 0.0
    wait, st, cnt = core.check_window(now + dt.timedelta(hours=1), now, 90, 100, 20)
    assert abs(wait - 23 * 3600) < 1 and st == now and cnt == 90
    # بعد از ۲۴ ساعت پنجره ریست می‌شه
    later = now + dt.timedelta(hours=25)
    assert core.check_window(later, now, 100, 100, 20) == (0.0, later, 0)


def test_format_status():
    job: dict = dict(id=3, source_title="A", dest_title="B", source_id=1, dest_id=2, status="running",
                     copied=50, skipped=2, total_hint=200, last_id=77, drop_author=True, last_error="")
    txt = core.format_status(job, {"state": "مکث", "t0": 0, "copied0": 0, "now": 100})
    assert "#3" in txt and "26%" in txt and "زمانِ باقی‌مانده" in txt and "#77" in txt
    assert "شروع از تاریخ" not in txt  # بدونِ تاریخ، خطِ جدا نباید بیاد
    assert "از این به بعد" not in txt
    # با تاریخِ شروع
    job["from_date"] = dt.datetime(2024, 7, 22, 10, 30)
    txt = core.format_status(job)
    assert "شروع از تاریخ: 1403/05/01 (2024/07/22) ساعت 10:30" in txt
    assert core.format_from_date(dt.datetime(2025, 3, 21)) == "1404/01/01 (2025/03/21)"
    # حالتِ «از این به بعد» و کپیِ چندکاناله
    job["watch"] = True
    job["children"] = "11,12,13"
    txt = core.format_status(job)
    assert "از این به بعد" in txt and "۳ کانال" not in txt and "3 کانالِ مبدأ" in txt
    assert core.STATUS_LABELS["watching"].startswith("از این به بعد")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok", f.__name__)
    print(f"{len(fns)} tests passed")
