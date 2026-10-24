"""
مدل‌های جدید برای قابلیت‌های افزوده‌شده:
- Inbox (صندوق ورودی هوشمند)
- Notification Rules (قوانین اعلان)
- User Profiles (پروفایل کاربران با برچسب‌ها)
- AI Memory (حافظه‌ی هوش مصنوعی)
- Automation Rules (موتور اتوماسیون)
- Settings (تنظیمات یکپارچه)
- Word Filter (فیلتر کلمات ممنوعه سفارشی)
- Gradual Warn System (سیستم هشدار تدریجی)
- Message Index (ایندکسِ پیام‌ها برای جستجوی معنایی)
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


# ------------------------------------------------------------- Inbox ---
class InboxItem(Base):
    """هر پیام ذخیره‌شده در صندوق ورودی."""

    __tablename__ = "inbox_items"
    __table_args__ = (
        Index("ix_inbox_items_chat_id", "chat_id"),
        Index("ix_inbox_items_read", "read"),
        Index("ix_inbox_items_importance", "importance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sender_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    sender_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0=normal, 1=important, 2=high
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # منحصربه‌فرد بودن (chat_id, message_id) برای جلوگیری از دوتا شدن
    __table_args__ = __table_args__ + (
        UniqueConstraint("chat_id", "message_id", name="uq_inbox_chat_message"),
    )


# ----------------------------------------------------- Notification Rules ---
class NotificationRule(Base):
    """قانون اعلان: شرط + عمل."""

    __tablename__ = "notification_rules"
    __table_args__ = (
        CheckConstraint("trigger_type IN ('message', 'keyword', 'user', 'time')", name="ck_notif_trigger_type"),
        CheckConstraint("action_type IN ('notify', 'save', 'forward', 'reply')", name="ck_notif_action_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger_value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON یا متن شرط
    action_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # پارامترهای عمل
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ------------------------------------------------------- User Profile ---
class UserProfile(Base):
    """اطلاعات تکمیلی کاربران (برچسب‌ها، یادداشت‌ها، VIP بودن)."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        Index("ix_user_profiles_user_id", "user_id"),
        Index("ix_user_profiles_tags", "tags"),  # for search
    )

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated: VIP, مشتری قدیمی, ...
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_vip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    added_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------------------- AI Memory ---
class AIMemory(Base):
    """حافظه‌ی هوش مصنوعی با دسته‌بندی."""

    __tablename__ = "ai_memory"
    __table_args__ = (
        Index("ix_ai_memory_category", "category"),
        Index("ix_ai_memory_key", "key"),
        UniqueConstraint("category", "key", name="uq_ai_memory_cat_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)  # کاربران, گفتگوها, پروژه‌ها, یادداشت‌ها, تنظیمات
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ------------------------------------------------------- Automation Rules ---
class AutomationRule(Base):
    """قوانین اتوماسیون: Event + Condition + Action."""

    __tablename__ = "automation_rules"
    __table_args__ = (
        CheckConstraint("event_type IN ('message', 'schedule', 'command', 'user_join', 'user_leave')", name="ck_auto_event"),
        CheckConstraint("action_type IN ('reply', 'ai', 'note', 'schedule', 'notify', 'guard', 'backup', 'autopost')", name="ck_auto_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    event_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # پارامترهای رویداد (JSON)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)  # شرط (مثلاً "keyword in message")
    action_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action_value: Mapped[str] = mapped_column(Text, nullable=False)  # پارامترهای عمل (JSON)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ------------------------------------------------------- Unified Settings (Key-Value) ---
class Setting(Base):
    """تنظیمات یکپارچه (key-value) برای هر چیزی که جدول خاص ندارد."""

    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("key", name="uq_settings_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

# ------------------------------------------------------------ Hafez Poems ---
class HafezPoem(Base):
    """
    دیوانِ حافظ (برای `.فال`) - یک‌بار با `scripts/seed_hafez.py` پر می‌شه و
    بعدش هندلر فقط از همین جدول یه ردیفِ رندوم می‌خونه؛ در زمانِ اجرایِ ربات
    هیچ پکیج/شبکه‌ی اضافه‌ای لازم نیست (برخلافِ نسخه‌ی قبلی که با پکیجِ
    `hafez` در همون لحظه import می‌شد).
    """

    __tablename__ = "hafez_poems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # همون poem_id گنجور/hafez
    poem: Mapped[str] = mapped_column(Text, nullable=False)  # ابیات، هر مصرع در یک خط
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)


# ------------------------------------------------------------ Word Filter (Group) ---
class GroupWordFilter(Base):
    """فیلتر کلمات ممنوعه سفارشی به‌ازای هر گروه."""

    __tablename__ = "group_word_filters"
    __table_args__ = (
        UniqueConstraint("chat_id", "word", name="uq_group_word_filters_chat_word"),
        Index("ix_group_word_filters_chat_id", "chat_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    word: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="delete")  # delete, warn, ban
    case_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_regex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ------------------------------------------------------- Gradual Warn System ---
class GroupUserWarning(Base):
    """شمارش هشدارهای هر کاربر در هر گروه."""

    __tablename__ = "group_user_warnings"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_group_user_warnings_chat_user"),
        Index("ix_group_user_warnings_chat_id", "chat_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_warn_time: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    muted_until: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    kicked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GroupWarnSettings(Base):
    """تنظیمات سیستم هشدار تدریجی برای هر گروه."""

    __tablename__ = "group_warn_settings"
    __table_args__ = (
        UniqueConstraint("chat_id", name="uq_group_warn_settings_chat_id"),
    )

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warn_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    action_on_limit: Mapped[str] = mapped_column(String(16), nullable=False, default="mute")  # mute, kick, ban
    mute_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    auto_reset_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ------------------------------------------------------- Group Activity Log ---
class GroupActivityLog(Base):
    """لاگ فعالیت روزانه گروه برای گزارش‌ها."""

    __tablename__ = "group_activity_log"
    __table_args__ = (
        Index("ix_group_activity_log_chat_id", "chat_id"),
        Index("ix_group_activity_log_date", "log_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    log_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    messages_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_given: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    members_joined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    members_left: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --------------------------------------------------------- Group Polls ---
class GroupPoll(Base):
    """نظرسنجی‌های ساخته‌شده با `.نظرسنجی` (برای بستن/جمع‌بندیِ بعدی)."""

    __tablename__ = "group_polls"
    __table_args__ = (
        Index("ix_group_polls_chat_id", "chat_id"),
        Index("ix_group_polls_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    poll_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list
    total_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------- Message Tracker Channels ---
class MessageTrackerChannel(Base):
    """لیستِ کانال‌های مقصدِ ردیابِ ویرایش/حذفِ پیام (`.ردیاب`)."""

    __tablename__ = "message_tracker_channels"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    added_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# -------------------------------------------------------- Price Alerts ---
class PriceAlert(Base):
    """هشدارِ قیمت (`.هشدارقیمت`) - وقتی قیمتِ یه قلم از TGJU به یه حدِ معین برسه، اطلاع می‌ده."""

    __tablename__ = "price_alerts"
    __table_args__ = (
        Index("ix_price_alerts_chat_id", "chat_id"),
        Index("ix_price_alerts_triggered", "triggered"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    item_label: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # "above" | "below"
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------- Escape Room ---
class EscapeSession(Base):
    """
    وضعیتِ بازیِ در جریانِ اتاق فرار (`.فرار`). هر (chat_id, user_id) دقیقاً
    یک رکورد دارد — جداسازیِ نشست‌ها با کلیدِ مرکب. کلِ state بازی به‌صورتِ
    JSON در ستونِ state ذخیره می‌شود (موتورِ بازی یک dict قابلِ JSON است)
    تا با هر restart از PostgreSQL برگردد.
    """

    __tablename__ = "escape_sessions"
    __table_args__ = (
        Index("ix_escape_sessions_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EscapeScore(Base):
    """نتیجه‌ی هر بازیِ تمام‌شده (برنده یا بازنده) برای leaderboard و آمار."""

    __tablename__ = "escape_scores"
    __table_args__ = (
        Index("ix_escape_scores_user_score", "user_id", "score"),
        Index("ix_escape_scores_won", "won"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scenario: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    solved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EscapeDaily(Base):
    """چالشِ روزانه: هر کاربر در هر روز فقط یک تلاش (`.فرار روزانه`)."""

    __tablename__ = "escape_daily"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", "day", name="uq_escape_daily_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    day: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------------------- Tasks ---
class TaskItem(Base):
    """کارِ شخصی (Task Manager): `.کار` - با ددلاینِ اختیاری."""

    __tablename__ = "task_items"
    __table_args__ = (
        Index("ix_task_items_done", "done"),
        Index("ix_task_items_due_at", "due_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 عادی / 1 مهم
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ------------------------------------------ Smart Inbox categories ---
# به InboxItem ستونِ needs_reply اضافه نمی‌کنیم (مایگریشنِ سنگین)؛ دسته‌بندیِ
# «نیازمند پاسخ» از روی priority + textِ ذخیره‌شده موقعِ triage به priority
# نگاشت می‌شود: 2=مهم 1=نیاز به پاسخ 0=عادی.


# ------------------------------------------------------ Channel Copy ---
class ChannelCopyTarget(Base):
    """اسمِ دلخواه برای یک کانالِ مقصد («ذخیره» توی `.کپی‌کانال`) — برای وقتی که آیدی نداریم."""

    __tablename__ = "channel_copy_targets"
    __table_args__ = (Index("ix_channel_copy_targets_name", "name", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChannelCopyJob(Base):
    """کارِ «کپی کانال» (`.کپی‌کانال`): پیشرفت ذخیره می‌شه تا بعد از ری‌استارت ادامه پیدا کنه."""

    __tablename__ = "channel_copy_jobs"
    __table_args__ = (Index("ix_channel_copy_jobs_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_ref: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dest_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dest_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dest_ref: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # آخرین message_id از مبدأ که پردازش شده (کپی شده یا ردشده)؛ ادامه از بعدِ همین
    last_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    copied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_hint: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # running | paused | done | error
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="paused")
    drop_author: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # پنجره‌ی ۲۴ساعته‌ی سقفِ روزانه
    window_start: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # تاریخِ شروعِ خواسته‌شده («از 1403/05/01»): datetimeِ بدونِ tz به وقتِ کاربر — فقط برایِ نمایش
    from_date: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    # «از این به بعد»: بعد از رسیدن به آخرِ مبدأ، منتظرِ پیام‌هایِ تازه می‌مونه و خودکار کپی می‌کنه
    watch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # کارِ «سازمان‌دهنده»: شناسه‌ی کارهای فرزند (با کاما) — برایِ کپیِ هم‌زمانِ چند کانال
    children: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ----------------------------------------------------------- Message Index ---
class MessageIndex(Base):
    """
    ایندکسِ پیام‌های تلگرام برای جستجوی معنایی (`.پرسش` درباره‌ی گفتگوهای قبلی).

    فقط پیام‌های متنی (یا کپشنِ رسانه) نگه داشته می‌شن. `embedding` بردارِ
    نرمال‌شده‌ی float16 (bytes) است؛ NULL یعنی هنوز embedding گرفته نشده
    (مثلاً سرویس در دسترس نبوده) و بعداً خودکار تکمیل می‌شه. `norm_text` نسخه‌ی
    نرمال‌شده‌ی فارسی (ی/ک، نیم‌فاصله، ارقام) برای جستجوی کلمه‌ایِ پشتیبان.
    """

    __tablename__ = "message_index"
    __table_args__ = (
        UniqueConstraint("chat_id", "message_id", name="uq_message_index_chat_msg"),
        Index("ix_message_index_chat_date", "chat_id", "date"),
        Index("ix_message_index_date", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chat_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chat_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="user")  # user / group / channel
    sender_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sender_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    norm_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embed_model: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
