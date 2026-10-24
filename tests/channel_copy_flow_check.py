#!/usr/bin/env python3
"""
تستِ یکپارچه‌ی «کپی کانال» با یک کلاینتِ ساختگی (بدونِ اتصال به تلگرام):
  • پیدا کردنِ کانالِ خصوصی با جستجو بینِ چت‌ها / با آیدیِ عددی / با پیامِ فوروارد
  • شروع از یک تاریخ (شمسی/میلادی) — منفرد و چندکاناله
  • حالتِ «از این به بعد» (watch) و ادامه‌ی خودکار برایِ کانالِ کپی‌شده
  • اسم‌های ذخیره‌شده («ذخیره» / «اسم‌ها»)
هیچ درخواستی به تلگرام زده نمی‌شه؛ فقط توابعِ هندلر با clientِ قلابی صدا زده می‌شن.
"""
import asyncio
import datetime as dt
import os
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "x")
os.environ.setdefault("PREFIX", ".")
os.environ.setdefault("TIMEZONE_OFFSET", "3.5")
DB = os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/channel_copy_flow.db")
if DB.startswith("sqlite"):
    try:
        os.remove("/tmp/channel_copy_flow.db")
    except FileNotFoundError:
        pass

from telethon.tl.types import Channel, Chat, PeerChannel, User  # noqa: E402

from bot import config  # noqa: E402
from bot.handlers import channel_copy as cc  # noqa: E402
from bot.repositories import channel_copy_repo as repo  # noqa: E402
from bot.db import models as _models, models_ext as _models_ext  # noqa: E402
from bot.db.engine import engine as _engine  # noqa: E402

# تست سریع باشه: مکثِ بینِ دسته‌ها و فاصله‌ی نگهبانیِ watch خیلی کم می‌شن
config.CHANNEL_COPY_DELAY_SECONDS = 0.01
config.CHANNEL_COPY_WATCH_SECONDS = 0.2
cc.config.CHANNEL_COPY_DELAY_SECONDS = 0.01
cc.config.CHANNEL_COPY_WATCH_SECONDS = 0.2

EPOCH = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)


def make_channel(cid, title, username=None, noforwards=False):
    """کانالِ واقعیِ Telethon (تا get_peer_id و isinstance کار کنه)."""
    return Channel(
        id=cid, title=title, photo=None,
        date=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
        creator=True, broadcast=True, megagroup=False, verified=False, restricted=False,
        signatures=False, min=False, scam=False, has_link=False, has_geo=False,
        slowmode_enabled=False, call_active=False, call_not_empty=False,
        noforwards=noforwards, join_request=False, access_hash=1,
        username=username, fake=False, gigagroup=False,
    )


class FakeClient:
    """کلاینتِ ساختگی با چند کانال (یکی خصوصی) و پیام‌های عددی."""

    def __init__(self, sizes: dict[int, int]):
        self.sizes = sizes
        self.forwarded: list[tuple[int, int]] = []   # (dest, msg_id)
        self.notices: list[str] = []
        self.get_messages_calls = 0
        self.get_dialogs_calls = 0
        self.entities = {
            cid: make_channel(cid, title, username) for cid, title, username in self.known
        }
        self.tmp_dialogs = [
            NS(entity=self.entities[cid], id=cid) for cid in sizes
        ]

    known: list = []

    async def get_dialogs(self, *a, **kw):
        self.get_dialogs_calls += 1
        folder = kw.get("folder")
        known = getattr(self, "folders_with_dialogs", None)
        if folder is not None and known is not None and folder not in known:
            return []                      # مثلِ تلگرام: پوشه‌ی ناموجود/خالی
        return list(self.tmp_dialogs)

    async def get_entity(self, ref):
        if isinstance(ref, str):
            key = ref.lstrip("@")
            for cid, ent in self.entities.items():
                if getattr(ent, "username", None) == key:
                    return ent
        key = getattr(ref, "channel_id", None) or ref
        if key in self.entities:
            return self.entities[key]
        raise ValueError(f"نامعتبر: {ref!r}")

    async def get_messages(self, peer, ids=None, limit=None, max_id=None, min_id=None):
        self.get_messages_calls += 1
        cid = getattr(peer, "id", peer)
        n = self.sizes.get(cid, 0)
        dates = {i: EPOCH + dt.timedelta(hours=i) for i in range(1, n + 1)}
        if ids is not None:
            ok = [i for i in ids if i in dates]
            return [NS(id=i, date=dates[i]) if i in dates else None for i in ids] or ok and []
        if limit == 1:
            if not n:
                return []
            return [NS(id=n, date=dates[n])]
        if limit == 0:
            if max_id is not None:
                cnt = len([i for i in dates if i < max_id])
            else:
                cnt = n
            out = []
            out.total = cnt
            return out
        return []

    async def forward_messages(self, dest, ids, **kw):
        d = getattr(dest, "id", dest)
        for i in ids:
            self.forwarded.append((d, i))
        return [NS(id=i) for i in ids]

    def iter_messages(self, peer, min_id=0, reverse=False, **kw):
        """مثلِ Telethon: از min_id (انحصاری) به بعد، صعودی."""
        cid = getattr(peer, "id", peer)
        n = self.sizes.get(cid, 0)
        items = [NS(id=i, date=EPOCH + dt.timedelta(hours=i), grouped_id=None, action=None)
                 for i in range(int(min_id) + 1, n + 1)]

        async def _gen():
            for m in items:
                yield m
        return _gen()

    async def send_message(self, who, text, **kw):
        self.notices.append(text)
        return NS(id=0)

    async def __call__(self, req, *a, **kw):
        name = type(req).__name__
        if name == "GetDialogFiltersRequest":
            return NS(filters=list(getattr(self, "filters", [])))
        if name == "CheckChatInviteRequest":
            return NS(chat=None, about="inviter", title=getattr(self, "invite_title", ""))
        raise RuntimeError(f"درخواستِ ناشناخته: {name}")

    async def get_permissions(self, ent, *a, **kw):
        return NS(is_creator=True, is_admin=True, post_messages=True, send_messages=True)


class FakePattern:
    def __init__(self, arg): self._arg = arg
    def group(self, i): return self._arg if i == 1 else ""


class FakeEvent:
    def __init__(self, arg, reply=None):
        self.pattern_match = FakePattern(arg)
        self._reply = reply
        self.edits = []
        self.chat_id, self.sender_id = 10, 1

    async def edit(self, text=None, **kw):
        self.edits.append(text or "")
        return NS(id=1, edit=self.edit)

    async def get_reply_message(self):
        return self._reply

    @property
    def last(self):
        return self.edits[-1] if self.edits else ""


async def create_schema():
    async with _engine.begin() as conn:
        await conn.run_sync(_models.Base.metadata.create_all)
        await conn.run_sync(_models_ext.Base.metadata.create_all)


async def run_cmd(fake, arg, reply=None):
    ev = FakeEvent(arg, reply)
    await cc.channel_copy_handler(ev)
    return ev.last


async def drain(timeout=60.0):
    """همه‌ی تسک‌های در حالِ اجرا رو متوقف می‌کنه و صبر می‌کنه تموم بشن."""
    for jid in list(cc._TASKS):
        ev = cc._STOP.get(jid)
        if ev is not None:
            ev.set()
    await wait_jobs(timeout)


async def dump_jobs(tag=""):
    rows = await repo.list_jobs(6)
    print(f"--- jobs {tag} ---")
    for j in rows:
        print(f"  #{j['id']} {j['source_title'][:22]!r} st={j['status']} copied={j['copied']} "
              f"watch={j['watch']} children={j['children']!r} err={j['last_error'][:60]!r}")


async def wait_jobs(timeout=20.0):
    """تا تموم‌شدنِ تسک‌های کپی صبر می‌کنه."""
    t0 = asyncio.get_event_loop().time()
    while cc._TASKS:
        if asyncio.get_event_loop().time() - t0 > timeout:
            raise TimeoutError(f"تسک‌ها تمام نشدن: {list(cc._TASKS)}")
        await asyncio.sleep(0.05)


CH_PRIVATE = -1001234567890   # کانالِ خصوصیِ بدونِ یوزرنیم
CH_PUBLIC = -1007777777777    # کانالِ عمومی
CH_DEST = -1005555555555      # کانالِ مقصد
CH_DEST2 = -1004444444444     # کانالِ مقصدِ دوم (برایِ تستِ «از این به بعد» بدونِ پیشرفتِ قبلی)


def new_fake(sizes):
    FakeClient.known = [
        (1234567890, "اخبارِ خصوصی", None),
        (7777777777, "کانالِ عمومی", "public_news"),
        (5555555555, "مقصد", "my_dest"),
        (4444444444, "مقصدِ دو", "my_dest2"),
    ]
    fc = FakeClient(sizes)
    fc.entities[CH_PRIVATE] = fc.entities[1234567890]
    fc.entities[CH_PUBLIC] = fc.entities[7777777777]
    fc.entities[CH_DEST] = fc.entities[5555555555]
    fc.entities[-1001234567890] = fc.entities[1234567890]
    fc.entities[-1007777777777] = fc.entities[7777777777]
    fc.entities[-1005555555555] = fc.entities[5555555555]
    fc.entities[CH_DEST2] = fc.entities[4444444444]
    fc.entities[-1004444444444] = fc.entities[4444444444]
    fc.tmp_dialogs = [
        NS(entity=fc.entities[1234567890], id=1234567890),
        NS(entity=fc.entities[7777777777], id=7777777777),
        NS(entity=fc.entities[5555555555], id=5555555555),
        NS(entity=fc.entities[4444444444], id=4444444444),
    ]
    return fc


def check(name, cond, extra=""):
    print(("✅" if cond else "❌"), name, extra if not cond else "")
    return bool(cond)


async def main():
    await create_schema()
    results = []

    # ۱) پیدا کردنِ کانالِ خصوصی با جستجو
    fake = new_fake({1234567890: 300, 7777777777: 300, 5555555555: 0, 4444444444: 0})
    cc.client = fake
    out = await run_cmd(fake, "پیدا خصوصی")
    results.append(check("جستجوی کانالِ خصوصی با اسمِ فارسی", "اخبارِ خصوصی" in out and str(CH_PRIVATE) in out, out))

    # ۲) ذخیره‌ی اسم + شروع با اسم
    out = await run_cmd(fake, "ذخیره اخبار مهم t.me/c/1234567890")
    out2 = await run_cmd(fake, "ذخیره مقصد @my_dest")
    rows = await repo.list_targets()
    results.append(check("ذخیره‌ی اسمِ کانالِ خصوصی (اسمِ دوکلمه‌ای)",
                         "ذخیره شد" in out and "ذخیره شد" in out2 and len(rows) == 2,
                         f"{out!r} | {out2!r} | {rows}"))
    out = await run_cmd(fake, "اسم‌ها")
    results.append(check("لیستِ اسم‌های ذخیره‌شده", "اخبار" in out, out))

    # ۳) شروع با تاریخ (شمسی) روی کانالِ خصوصیِ ذخیره‌شده + ریپلای (آدرس نداریم)
    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع اخبار مهم مقصد")
    results.append(check("شروع با اسمِ ذخیره‌شده", "شروع شد" in out, out))
    await wait_jobs()
    n1 = len(fake.forwarded)
    results.append(check("کپیِ کاملِ کانالِ خصوصی (۳۰۰ پیام)", n1 == 300, f"کپی‌شده={n1}"))

    # ۴) از تاریخ به بعد (پیامِ ۲۰۰ = 2024-01-09 08:00 UTC = 11:30 تهران)
    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع اخبار مهم مقصد از 1403/02/01")   # 2024-04-20 → همه رد می‌شن
    results.append(check("تاریخِ خارج از بازه → پیامِ خطا", "پیدا نشد" in out or "هیچ کاری" in out, out))

    fake.forwarded.clear()
    from bot.channel_copy_core import find_start_id  # noqa: F401
    out = await run_cmd(fake, "شروع اخبار مهم مقصد از 2024-01-05")
    await wait_jobs()
    ids = sorted(i for _, i in fake.forwarded)
    results.append(check("شروع از تاریخِ میلادی (۲۰۲۴-۰۱-۰۵ → از پیامِ ۹۳)",
                         ids and ids[0] == 93 and ids[-1] == 300, ids[:2]))

    await drain()
    await dump_jobs("after-test-4")
    # ۵) «از این به بعد»: اول از ابتدا کپی می‌کنه، بعد پیام‌های تازه رو هم می‌گیره
    fake = new_fake({1234567890: 10, 7777777777: 10, 5555555555: 0, 4444444444: 0})
    cc.client = fake
    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع اخبار مهم @my_dest2 ازاین‌بعد")
    results.append(check("حالتِ «از این به بعد» اعلام می‌شه",
                         "شروع شد" in out and "از این به بعد" in out, out))
    for _ in range(40):                       # صبر تا کپیِ ۱۰ پیامِ اولیه
        if len(fake.forwarded) >= 10:
            break
        await asyncio.sleep(0.25)
    n_before = len(fake.forwarded)
    fake.sizes[1234567890] = 12               # دو پستِ تازه
    for _ in range(40):
        if len(fake.forwarded) >= 12:
            break
        await asyncio.sleep(0.25)
    jobs = await repo.list_jobs(3)
    watch_job = next((j for j in jobs if j["watch"]), None)
    results.append(check("کارِ watch ساخته شده", watch_job is not None))
    if watch_job:
        results.append(check("پیام‌های تازه هم کپی شدن (۱۲ از ۱۲)",
                             len(fake.forwarded) >= 12, f"{n_before} → {len(fake.forwarded)}"))
        results.append(check("وضعیتِ کار = watching",
                             watch_job["status"] in ("watching", "running"), watch_job["status"]))
        results.append(check("حالتِ «از این به بعد» در وضعیت نمایش داده می‌شه",
                             "از این به بعد" in (cc._status_text(watch_job) or ""),
                             cc._status_text(watch_job)))
    await drain()

    await drain()
    # ۶) چند کانال هم‌زمان + کارِ سازمان‌دهنده
    fake = new_fake({1234567890: 5, 7777777777: 7, 5555555555: 0, 4444444444: 0})
    cc.client = fake
    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع اخبار مهم,@public_news مقصد")
    await asyncio.sleep(0.2)
    results.append(check("چند کانال با هم (۲ کانالِ مبدأ)", "۲ کانالِ مبدأ" in out.replace("2 کانالِ مبدأ", "۲ کانالِ مبدأ"), out))
    await wait_jobs()
    results.append(check("مجموعِ پیام‌های دو کانال = ۱۲", len(fake.forwarded) == 12, len(fake.forwarded)))

    await drain()
    await dump_jobs("after-test-6")
    # ۷) پیامِ فورواردشده به‌عنوان مبدأ (کانالِ خصوصی، ریپلای)
    fake = new_fake({1234567890: 4, 7777777777: 4, 5555555555: 0, 4444444444: 0})
    cc.client = fake
    fake.forwarded.clear()
    reply = NS(id=2, peer_id=NS(channel_id=1234567890), fwd_from=NS(channel_post=2), get_sender=None)
    async def _gs():
        return fake.entities[1234567890]
    reply.get_sender = _gs
    out = await run_cmd(fake, "شروع @public_news مقصد", reply=None)
    await wait_jobs()
    results.append(check("کانالِ عمومی با یوزرنیم", len(fake.forwarded) == 4, len(fake.forwarded)))

    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع xyz مقصد", reply=reply)
    await wait_jobs()
    results.append(check("مبدأ از پیامِ فوروارد (کانالِ خصوصی)", len(fake.forwarded) == 4, f"{out} | {len(fake.forwarded)}"))


    # ۸) پوشه‌ها: خواندنِ اسم‌ها/شماره‌ها
    fake = new_fake({1234567890: 5, 7777777777: 6, 5555555555: 0, 4444444444: 0})
    fake.filters = [
        NS(id=7, title="اخبارها", include_peers=[]),
        NS(id=3, title=NS(text="خبری"), include_peers=[]),
    ]
    # «پوشه:N» با get_dialogs(folder=N) کار می‌کنه → اینجا همه‌ی چت‌ها رو برمی‌گردونیم
    cc.client = fake
    fake.folders_with_dialogs = {7}       # فقط پوشه‌ی ۷ کانال داره
    out = await run_cmd(fake, "پوشه‌ها")
    results.append(check("لیستِ پوشه‌ها با شماره",
                         "اخبارها" in out and "7" in out and "خبری" in out and "3" in out, out))
    results.append(check("راهنمای استفاده از پوشه در لیست", "پوشه:1" in out, out))
    out = await run_cmd(fake, "شروع پوشه:9 مقصد")
    await drain()
    results.append(check("پوشه‌ی ناموجود/خالی → پیامِ خطا", "پیدا نشد" in out or "⛔" in out or "خالی" in out, out))

    # کپیِ همه‌ی کانال‌های یک پوشه (مقصد از دامنه حذف می‌شه)
    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع پوشه:7 مقصد")
    await wait_jobs(60)          # صبر تا تموم‌شدنِ همه‌ی کانال‌های پوشه
    results.append(check("شروع با پوشه:N — همه‌ی کانال‌های پوشه کپی می‌شن",
                         "شروع شد" in out and len(fake.forwarded) == 11,
                         f"{out[:80]!r} | {len(fake.forwarded)}"))
    kids = [await repo.get_job(j["id"]) for j in await repo.list_jobs(2)]
    parent = next((k for k in kids if k["children"]), None)
    results.append(check("کارِ سازمان‌دهنده‌ی پوشه ساخته و تمام شد",
                         parent is not None and parent["status"] == "done" and parent["copied"] == 11,
                         f"{(parent or {}).get('status')} {(parent or {}).get('copied')}"))

    # تستِ استخراجِ لینک از متنِ ریپلای (پستِ معرفیِ کانال) → مبدأ
    fake = new_fake({1234567890: 3, 7777777777: 3, 5555555555: 0, 4444444444: 0})
    cc.client = fake
    fake.forwarded.clear()
    intro = NS(id=99, fwd_from=None, message="کانالِ جدید: t.me/c/1234567890/2",
               entities=[], peer_id=NS(channel_id=0), get_sender=None)
    async def _gs2():
        raise ValueError("no sender")
    intro.get_sender = _gs2
    out = await run_cmd(fake, "شروع xyz مقصد", reply=intro)
    await wait_jobs()
    results.append(check("مبدأ از لینکِ خصوصیِ داخلِ متنِ ریپلای",
                         len(fake.forwarded) == 3, f"{out[:70]!r} | {len(fake.forwarded)}"))


    await drain()
    # ۱۰) سناریویِ گزارش‌شده‌ی کاربر: ریپلای روی پستِ کانالِ خصوصی + «شروع @مقصد» (یک آدرس)
    fake = new_fake({1234567890: 4, 7777777777: 4, 5555555555: 0, 4444444444: 0})
    cc.client = fake
    fake.forwarded.clear()
    post = NS(id=3, peer_id=NS(channel_id=1234567890, user_id=None),
              fwd_from=NS(channel_post=3), message="پستِ کانال", entities=[], get_sender=None)

    async def _sender():
        return fake.entities[1234567890]
    post.get_sender = _sender
    out = await run_cmd(fake, "شروع @my_dest", reply=post)
    await wait_jobs()
    results.append(check("ریپلای روی پستِ کانال خصوصی + «شروع @مقصد» شروع می‌شود",
                         "شروع شد" in out and len(fake.forwarded) == 4,
                         f"{out[:90]!r} | {len(fake.forwarded)}"))
    job = (await repo.list_jobs(1))[0]
    results.append(check("مبدأ همان کانالِ ریپلای‌شده ثبت شده",
                         job["source_id"] == -1001234567890 and job["dest_id"] == -1005555555555,
                         f"{job['source_id']} → {job['dest_id']}"))

    # «از <تاریخِ محلی>» با مبدأِ ریپلای: 05:00 به وقتِ تهران = 01:30 UTC → از پیامِ ۲
    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع @my_dest از 2024-01-01 05:00", reply=post)
    await wait_jobs()
    results.append(check("«شروع @مقصد از <تاریخ>» + ریپلای → از همان تاریخ کپی می‌کند",
                         "شروع شد" in out and sorted(i for _, i in fake.forwarded) == [2, 3, 4],
                         f"{out[:80]!r} | {sorted(i for _, i in fake.forwarded)}"))

    # بدونِ ریپلای و با یک آدرس → خطای راهنما (نه فقط راهنما)
    await drain()
    out = await run_cmd(fake, "شروع @my_dest", reply=None)
    results.append(check("یک آدرس بدونِ ریپلای → پیامِ راهنما",
                         "ریپلای" in out and "شروع شد" not in out, out))

    # با تاریخ و مبدأِ ریپلای (از پیامِ ۳ به بعد) و مقصد از ریپلای‌داخلِ کانالِ مقصد
    fake.forwarded.clear()
    in_dest = NS(id=1, peer_id=NS(channel_id=5555555555, user_id=None),
                 fwd_from=None, message="", entities=[], get_sender=None)
    async def _gs3():
        return fake.entities[5555555555]
    in_dest.get_sender = _gs3
    out = await run_cmd(fake, "شروع از 2024-01-01 03:00", reply=post)
    await wait_jobs()
    results.append(check("«شروع از <تاریخ>» بدونِ مقصد + ریپلایداخلِکانالِمقصد → راهنمای مقصد",
                         "مقصد" in out, f"{out[:110]!r}"))
    await drain()


    # ۱۱) سناریویِ دومِ کاربر: پستی که به پیوی فوروارد شده و متنش لینکِ دعوتِ
    #     خصوصی داره → نباید خطای داخلی بده و باید کاربر را راهنمایی کنه
    await drain()
    fake = new_fake({1234567890: 4, 7777777777: 4, 5555555555: 0, 4444444444: 0})
    cc.client = fake
    fake.invite_title = "اخبارِ خصوصی"     # اسمی که CheckChatInvite برمی‌گردونه
    fake.forwarded.clear()
    invite_txt = "عضویت در کانال: https://t.me/+AbCdEf123"
    fwd_post = NS(id=4, peer_id=NS(channel_id=None, user_id=None),
                  fwd_from=NS(channel_post=4, from_id=None, from_name="اخبارِ خصوصی"),
                  message=invite_txt, entities=[], get_sender=None)
    async def _no_sender():
        raise ValueError("Cannot find the input entity")
    fwd_post.get_sender = _no_sender
    out = await run_cmd(fake, "شروع @my_dest", reply=fwd_post)
    results.append(check("پستِ فورواردشده با لینکِ دعوت → بدونِ خطای داخلی",
                         "❌" not in out and "خطا در پیدا کردنِ کانال" not in out, out))
    results.append(check("همون پست → کانالِ هم‌نام از چت‌ها پیدا و کپی شروع می‌شود",
                         "شروع شد" in out and len(fwd_post.__dict__) > 0, out[:90]))

    # لینکِ دعوتی که کانالِ هم‌نام در چت‌ها نیست → پیامِ روشنِ «عضو شو»
    await drain()
    fake2 = new_fake({1234567890: 4, 7777777777: 4, 5555555555: 0, 4444444444: 0})
    cc.client = fake2
    fake2.invite_title = "کانالِ ناشناس"
    out = await run_cmd(fake2, "شروع @my_dest", reply=fwd_post)
    results.append(check("لینکِ دعوتِ ناشناس → پیامِ «اول باید عضوش باشی»",
                         "عضوش باشی" in out and "❌" not in out, out))

    # pستِ فورواردی که از_id داره و get_sender نمی‌ده → مبدأ از هدرِ فوروارد
    await drain()
    fake3 = new_fake({1234567890: 4, 7777777777: 4, 5555555555: 0, 4444444444: 0})
    cc.client = fake3
    fake3.forwarded.clear()
    from telethon.tl.types import PeerChannel
    fwd2 = NS(id=5, peer_id=NS(channel_id=None, user_id=None),
              fwd_from=NS(channel_post=5, from_id=PeerChannel(1234567890), from_name="اخبارِ خصوصی"),
              message="", entities=[], get_sender=None)
    fwd2.get_sender = _no_sender
    out = await run_cmd(fake3, "شروع @my_dest", reply=fwd2)
    await wait_jobs()
    results.append(check("مبدأ از هدرِ فوروارد (fwd_from.from_id) حل می‌شود",
                         "شروع شد" in out and len(fake3.forwarded) == 4,
                         f"{out[:80]!r} | {len(fake3.forwarded)}"))


    # ۱۲) «ادامه» روی کارِ تمام‌شده: فقط پست‌های تازه‌ی بعدی کپی می‌شن
    await drain()
    fake = new_fake({1234567890: 5, 7777777777: 5, 5555555555: 0, 4444444444: 0})
    cc.client = fake
    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع اخبار مهم مقصد")
    await wait_jobs()
    n1 = len(fake.forwarded)
    job = (await repo.list_jobs(1))[0]
    done = await repo.get_job(job["id"])
    results.append(check("کپیِ اولیه تمام شد و last_id ثبت شد",
                         done["status"] == "done" and done["last_id"] == 5 and n1 == 5,
                         f"{done['status']} last={done['last_id']} n={n1}"))

    # حالا مبدأ دو پستِ تازه می‌ذاره
    fake.forwarded.clear()
    fake.sizes[1234567890] = 7
    out = await run_cmd(fake, f"ادامه {job['id']}")
    await wait_jobs()
    ids = sorted(i for _, i in fake.forwarded)
    results.append(check("«ادامه N» روی کارِ تمام‌شده فقط پست‌های تازه را کپی می‌کند",
                         ids == [6, 7], f"{out[:70]!r} | {ids}"))
    results.append(check("از ادامه‌دادن هم ۰ پیامِ تکراری کپی نشد", 1 not in ids and 5 not in ids, ids))
    after = await repo.get_job(job["id"])
    results.append(check("پیشرفتِ کار تجمعی ماند (copied=7)", after["copied"] == 7, after["copied"]))
    out2 = await run_cmd(fake, f"ادامه {job['id']}")
    await wait_jobs()
    results.append(check("«ادامه» دوباره بدونِ پستِ تازه → ۰ کپی", len(fake.forwarded) == 2, len(fake.forwarded)))

    # همین رفتار برای کارِ گروهی: ادامه‌دادن همه‌ی بچه‌ها
    fake.forwarded.clear()
    out = await run_cmd(fake, "شروع اخبار مهم,@public_news مقصد")
    await wait_jobs()
    parent = next((j for j in await repo.list_jobs(3) if j["children"]), None)
    results.append(check("کارِ گروهی ساخته شد", parent is not None))
    fake.forwarded.clear()
    fake.sizes[1234567890] = 9
    fake.sizes[7777777777] = 8
    out = await run_cmd(fake, f"ادامه {parent['id']}")
    await wait_jobs()
    ids = sorted(i for _d, i in fake.forwarded)
    # اخبار: ۸ و ۹ (last_id=7 بود) • عمومی: ۶ و ۷ و ۸ (last_id=5 بود) → ۵ پیام، بدونِ تکرار برای هر مبدأ
    results.append(check("«ادامه» روی کارِ گروهی، فقط پست‌های تازه‌ی هر دو کانال را کپی می‌کند",
                         len(ids) == 5 and sorted(set(ids)) == [6, 7, 8, 9] and ids.count(8) == 2,
                         f"{out[:60]!r} | {ids}"))
    kids = await repo.list_children(parent["id"])
    results.append(check("پیشرفتِ بچه‌ها تجمعی ماند (۹ و ۸)",
                         sorted(k["copied"] for k in kids) == [8, 9],
                         [(k["source_title"], k["copied"], k["last_id"]) for k in kids]))

    # ۹) مبدأ لینکِ دعوتِ خصوصی (بدونِ عضویت): باید پیامِ راهنما بده
    out = await run_cmd(fake, "شروع +AbCdEf123 مقصد")
    results.append(check("لینکِ دعوتِ خصوصی → راهنما (عضو شو یا ریپلای)",
                         "عضوش باشی" in out or "ریپلای" in out or "دعوت" in out, out))

    print()
    print(f"{sum(results)}/{len(results)} تست موفق")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
