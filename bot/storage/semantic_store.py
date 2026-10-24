"""تنظیماتِ ایندکسِ پیام‌ها (جستجوی معنایی) - جدولِ عمومیِ settings (key-value).

روشن/خاموشِ کلی (semantic_index_enabled) و مسیریابیِ خودکارِ `.پرسش`
(semantic_auto_route) توی bot/storage/settings_toggles.py هستن؛ اینجا فقط
«دامنه‌ی ایندکس» (چه نوع چت‌هایی) و «چت‌های مستثنی» نگه داشته می‌شه.
"""
from ..repositories import settings_repo

SCOPES = ("private", "groups", "all")  # فقط پیوی / پیوی+گروه / همه (با کانال)

semantic_state = {"scope": "private", "excluded": set()}

_K_SCOPE = "semantic_scope"
_K_EXCLUDED = "semantic_excluded_chats"


async def init_semantic_state() -> None:
    scope = await settings_repo.get_setting(_K_SCOPE)
    if scope in SCOPES:
        semantic_state["scope"] = scope
    raw = await settings_repo.get_setting(_K_EXCLUDED) or ""
    semantic_state["excluded"] = {int(x) for x in raw.split(",") if x.strip().lstrip("-").isdigit()}


async def set_scope(scope: str) -> None:
    if scope not in SCOPES:
        raise ValueError(f"دامنه‌ی نامعتبر: {scope}")
    semantic_state["scope"] = scope
    await settings_repo.set_setting(_K_SCOPE, scope)


async def _save_excluded() -> None:
    await settings_repo.set_setting(_K_EXCLUDED, ",".join(str(x) for x in sorted(semantic_state["excluded"])))


async def exclude_chat(chat_id: int) -> None:
    semantic_state["excluded"].add(chat_id)
    await _save_excluded()


async def include_chat(chat_id: int) -> bool:
    if chat_id in semantic_state["excluded"]:
        semantic_state["excluded"].discard(chat_id)
        await _save_excluded()
        return True
    return False


def is_excluded(chat_id: int) -> bool:
    return chat_id in semantic_state["excluded"]
