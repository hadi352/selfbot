"""
ثبت تمام هندلرهای دستورات سلف‌بات.
هر فایل جدید باید در اینجا import شود تا دکوریتورهای @client.on فعال شوند.
"""

# هندلرهای اصلی
from . import (
    admin,
    ai,
    assistant,
    audio,
    autopost,
    backup,
    command_router,
    convert,
    daily_digest,
    font,
    fun,
    general,
    groupguard,
    help,
    media,
    messages,
    notes,
    ocr,
    ocr_translate,
    panel,
    poll,
    profile,
    scheduler,
    stats,
    stats_graph,
    tools,
)

# هندلرهای جدید (v9.3+)
from . import (
    health,
    settings_center,
    inbox,
    smart_reply,
    ai_memory,
    global_search,
    notifications,
    automation,
    plugins_cmd,
    message_tracker,
    price_alert,
    recurring,
    extras,
    escape,
)

# هندلرهای دستیار شخصی (v10)
from . import (
    tasks,
    autopilot,
    dashboard,
    security,
    gamification,
    knowledge,
    semantic,
)

# کپی کانال
from . import channel_copy