"""تستِ منطقِ جستجوی معنایی (bot/semantic_search.py) — بدونِ دیتابیس/تلگرام/شبکه.

repo با یک نسخه‌ی درون‌حافظه‌ای و embedding با یک مدلِ «مفهومی»ِ ساختگی جایگزین می‌شه
(هر گروه از کلمات یک بُعد) تا ثابت بشه جستجو بدونِ هم‌پوشانیِ کلمه‌ها هم کار می‌کنه.
"""
import asyncio
import datetime as dt
import os
import sys
import zlib
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "x")
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
os.environ["AI_EMBED_API_KEY"] = "test-key"
os.environ["TIMEZONE_OFFSET"] = "3.5"

import numpy as np  # noqa: E402

from bot import semantic_search as ss  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 18, 12, 0, tzinfo=UTC)

# ----------------------------------------------------------- ساختگی‌ها ---
CONCEPTS = [
    {"گوشی", "موبایل", "آیفون", "سامسونگ", "iphone"},
    {"خرید", "بخرم", "بخریم", "بخر", "قیمت", "پول"},
    {"سفر", "بلیط", "هتل", "مسافرت"},
    {"غذا", "ناهار", "پیتزا", "شام"},
]


_NOISE = 256


def fake_embed(text: str) -> np.ndarray:
    toks = set(ss.normalize_text(text).split())
    toks |= {t.rstrip("ی") for t in toks}
    v = np.zeros(len(CONCEPTS) + _NOISE, dtype=np.float32)
    all_concept = set().union(*CONCEPTS)
    for i, group in enumerate(CONCEPTS):
        v[i] = sum(1 for t in toks if t in group)
    for t in toks - all_concept:  # کلماتِ خارج از مفاهیم: نویزِ هش‌شده (کلماتِ مشترک = شباهتِ کم)
        v[len(CONCEPTS) + zlib.crc32(t.encode()) % _NOISE] += 0.25
    v[len(CONCEPTS)] += 0.01  # بردارِ صفر نشه
    return v / np.linalg.norm(v)


async def _fake_embed_texts(texts):
    return [fake_embed(t) for t in texts]


class FakeRepo:
    def __init__(self, rows):
        self.rows = rows

    async def count_all(self):
        return len(self.rows)

    async def known_names(self, limit=4000):
        return list({(r.chat_id, r.chat_title, r.sender_id, r.sender_name) for r in self.rows})

    async def lexical_candidates(self, tokens, *, limit=300, date_from=None, date_to=None):
        out = [
            r for r in self.rows
            if any(t in r.norm_text for t in tokens)
            and (not date_from or r.date >= date_from)
            and (not date_to or r.date <= date_to)
        ]
        return sorted(out, key=lambda r: r.date, reverse=True)[:limit]

    async def get_by_ids(self, ids):
        ids = set(ids)
        return [r for r in self.rows if r.id in ids]

    async def context_window(self, chat_id, date, *, before=4, after=4):
        same = sorted([r for r in self.rows if r.chat_id == chat_id], key=lambda r: (r.date, r.message_id))
        idx = max(i for i, r in enumerate(same) if r.date <= date)
        return same[max(0, idx - before): idx + 1 + after]

    async def fetch_embeddings(self, model, *, after_id=0, limit=5000):
        return [
            (r.id, r.chat_id, r.date, r.embedding)
            for r in sorted(self.rows, key=lambda r: r.id)
            if r.id > after_id and r.embedding is not None and r.embed_model == model
        ][:limit]


_ID = 0


def row(chat_id, chat_title, sender_id, sender_name, text, when, *, is_out=False):
    global _ID
    _ID += 1
    return SimpleNamespace(
        id=_ID, chat_id=chat_id, message_id=_ID, chat_title=chat_title, chat_username=None,
        chat_kind="user", sender_id=sender_id, sender_name=sender_name, is_out=is_out, text=text,
        norm_text=ss.normalize_text(text), date=when,
        embedding=ss.pack_vector(fake_embed(text)), embed_model=ss.embed_tag(),
    )


def make_world():
    d = lambda days, h=20, m=0: NOW - dt.timedelta(days=days) + dt.timedelta(hours=h - 12, minutes=m)
    return [
        # علی: گفتگوی گوشی، ~۶۰ روز پیش (بدونِ کلمه‌ی «خرید گوشی» به همین شکل)
        row(1, "علی رضایی", 11, "علی رضایی", "سلام داداش چطوری", d(61, 20, 0)),
        row(1, "علی رضایی", 11, "علی رضایی", "میخوام یه موبایل جدید بخرم، آیفون یا سامسونگ؟", d(61, 20, 5)),
        row(1, "علی رضایی", 99, "من", "به نظرم سامسونگ بخر، قیمتش بهتره", d(61, 20, 9), is_out=True),
        row(1, "علی رضایی", 11, "علی رضایی", "باشه ممنون، فردا میرم میخرم", d(61, 20, 15)),
        # علی: یک گفتگوی قدیمی‌تر دربارهٔ گوشی (۲۰۰ روز پیش)
        row(1, "علی رضایی", 11, "علی رضایی", "گوشیم خراب شده باید بخرم یکی جدید", d(200, 18, 0)),
        # سارا: سفر
        row(2, "سارا", 22, "سارا", "بلیط هتل رو رزرو کردی؟ مسافرت نزدیکه", d(10, 15, 0)),
        row(2, "سارا", 99, "من", "آره دیروز بلیط‌ها رو گرفتم", d(10, 15, 3), is_out=True),
        # مریم: گفتگوی گوشی ۳ روز پیش
        row(3, "مریم", 33, "مریم", "قیمت آیفون جدید چنده؟ میخوام گوشی بخرم", d(3, 19, 0)),
        # غذا
        row(4, "گروه دوستان", 44, "رضا", "ناهار پیتزا بخوریم؟", d(2, 13, 0)),
    ]


def run(coro):
    return asyncio.run(coro)


def setup_module(_=None):
    ss.cache.reset()
    ss.embed_texts = _fake_embed_texts
    ss.embeddings_enabled = lambda: True


# ---------------------------------------------------------------- تست‌ها ---
def test_normalize_and_tokenize():
    assert ss.normalize_text("علي و كتاب‌ها ۱۲۳ https://x.com/a") == "علی و کتاب ها 123"
    assert "گوشی" in ss.tokenize(ss.normalize_text("گوشی‌ها"), query=True) or "گوشی" in ss.tokenize("گوشی ها")
    assert ss.tokenize("آخرین باری که درباره خرید گوشی", query=True) == ["خرید", "گوشی"]


def test_recall_detection():
    assert ss.looks_like_recall("آخرین باری که درباره خرید گوشی صحبت کردم چی گفتیم؟")
    assert ss.looks_like_recall("با علی درباره سفر چی گفتیم")
    assert ss.looks_like_recall("توی چت علی کی گفت که میره مسافرت؟")
    assert not ss.looks_like_recall("گاندی درباره عدم خشونت چی گفت؟")  # سوالِ عمومی، نه گفتگوی شخصی
    assert not ss.looks_like_recall("کی گفت من آمدم ای دوست")
    assert not ss.looks_like_recall("پایتخت فرانسه کجاست؟")
    assert not ss.looks_like_recall("یه رسپی ساده برای املت بده")
    assert ss.wants_latest("آخرین باری که صحبت کردیم")


def test_topic_extraction():
    assert ss.topic_of_question("آخرین باری که درباره خرید گوشی صحبت کردم چی گفتیم؟") == "خرید گوشی"


def test_time_hint():
    h = ss.parse_time_hint("دو ماه پیش با علی چی گفتیم", NOW)
    assert h and h.start < NOW - dt.timedelta(days=60) < h.end
    assert ss.parse_time_hint("چند ماه پیش", NOW) is None
    y = ss.parse_time_hint("دیروز چی گفتیم", NOW)
    assert y and y.end - y.start == dt.timedelta(days=1)


def test_people_matching():
    names = [(1, "علی رضایی", 11, "علی رضایی"), (2, "سارا", 22, "سارا"), (5, "علیرضا", 55, "علیرضا")]
    chats, senders, labels = ss.match_people("با علی درباره گوشی صحبت کردم", names)
    assert chats == {1} and senders == {11}  # «علی» با «علیرضا» اشتباه نمی‌شه
    assert ss.match_people("درباره گوشی", names)[0] == set()


def test_date_format():
    assert ss.format_date_fa(NOW, with_time=False) == "۲۶ مهر ۱۴۰۵"
    assert ss.age_fa(NOW - dt.timedelta(days=61), NOW) == "۲ ماه پیش"


def test_semantic_search_finds_by_meaning_and_prefers_latest():
    setup_module()
    ss._REPO_OVERRIDE = FakeRepo(make_world())
    res = run(ss.search("آخرین باری که درباره خرید گوشی صحبت کردم چی گفتیم؟", now=NOW))
    assert res.used_semantic and res.windows
    # «آخرین بار» → جدیدترین گفتگوی مرتبط (مریم، ۳ روز پیش) اول
    assert res.windows[0].title == "مریم"
    titles = [w.title for w in res.windows]
    assert "علی رضایی" in titles  # گفتگوی ۶۱ روز پیش (بدونِ هم‌پوشانیِ کلمه‌ای با سوال) هم پیدا شده
    assert "سارا" not in titles and "گروه دوستان" not in titles
    ali = next(w for w in res.windows if w.title == "علی رضایی")
    texts = [m.text for m in ali.messages]
    assert any("سامسونگ بخر" in t for t in texts)  # context اطراف
    assert ali.messages == sorted(ali.messages, key=lambda m: m.date)


def test_person_filter_and_time_hint():
    setup_module()
    ss._REPO_OVERRIDE = FakeRepo(make_world())
    res = run(ss.search("با علی دو ماه پیش درباره گوشی چی گفتیم", now=NOW))
    assert [w.title for w in res.windows] == ["علی رضایی"]
    assert res.people == ["علی رضایی"] and res.time_hint is not None and not res.relaxed_time
    assert abs((ss.to_local(res.windows[0].best.row.date) - ss.to_local(NOW)).days) > 50


def test_time_hint_relaxes_when_empty():
    setup_module()
    ss._REPO_OVERRIDE = FakeRepo(make_world())
    res = run(ss.search("دیروز درباره بلیط هتل چی گفتیم", now=NOW))  # سفر ۱۰ روز پیش بوده، نه دیروز
    assert res.windows and res.windows[0].title == "سارا" and res.relaxed_time


def test_no_match_returns_empty():
    setup_module()
    ss._REPO_OVERRIDE = FakeRepo(make_world())
    res = run(ss.search("با سارا درباره فوتبال چی گفتیم", now=NOW))
    assert res.windows == [] and res.total_indexed == 9


def test_lexical_fallback_without_embeddings():
    ss._REPO_OVERRIDE = FakeRepo(make_world())
    ss.embeddings_enabled = lambda: False

    async def _no_expand(q):
        return []
    ss.expand_query = _no_expand
    res = run(ss.search("درباره خرید گوشی", now=NOW))
    assert not res.used_semantic and res.windows
    assert res.windows[0].title == "مریم"  # «میخوام گوشی بخرم»/«خرید» + «گوشی» → بیشترین هم‌پوشانی
    assert all(w.title in ("مریم", "علی رضایی") for w in res.windows)
    setup_module()


def test_prompt_has_sources_and_me():
    setup_module()
    ss._REPO_OVERRIDE = FakeRepo(make_world())
    res = run(ss.search("با علی درباره گوشی چی گفتیم", now=NOW))
    msgs = ss.build_prompt("با علی درباره گوشی چی گفتیم", res)
    user = msgs[1]["content"]
    assert "[1] چت با «علی رضایی»" in user and "من: به نظرم سامسونگ بخر" in user
    assert "نادیده بگیر" in msgs[0]["content"]  # محافظ در برابرِ prompt injection


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:  # noqa: BLE001
                fails += 1
                import traceback
                traceback.print_exc()
                print("FAIL", name, repr(e))
    sys.exit(1 if fails else 0)
