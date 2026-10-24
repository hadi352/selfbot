"""
Telegram Selfbot (Userbot) - نسخه فارسی
ساخته‌شده با Telethon - نسخه‌ی ماژولار

نکات مهم امنیتی/قانونی:
- این اسکریپت با اکانت شخصی تلگرام شما وارد می‌شه (نه یک بات جدا از BotFather)
- فقط پیام‌هایی که خودتون (owner) بفرستید به‌عنوان دستور اجرا می‌شن
- استفاده افراطی از دستورات، مخصوصاً ساعت زنده با فاصله خیلی کم، یا اسپم و
  ادعای عضویت انبوه ممکنه باعث محدودیت اکانت توسط تلگرام بشه. مقادیر پیش‌فرض
  رعایت شده تا ریسک این موضوع کم باشه.
- دستورات مدیریتی (kick/ban/promote/demote) رو فقط توی گروه‌هایی که خودتون
  ادمین هستید استفاده کنید.

ساختار پروژه (ماژولار):
    bot/config.py            تنظیمات (از .env / متغیرهای محیطی Railway)
    bot/runtime.py           نمونه‌ی TelegramClient + سشن HTTP مشترک
    bot/utils.py             ساخت الگوی دستورات (pat)
    bot/calc.py              ماشین‌حساب امن
    bot/fonts.py             فونت‌های پیام
    bot/clock.py             ساعت زنده در نام پروفایل + تسک پس‌زمینه
    bot/db/                  اتصال PostgreSQL (SQLAlchemy async) + ORM models
    bot/repositories/        Repository/Database Layer (تنها لایه‌ای که SQL می‌زنه)
    bot/storage/             آداپتورهای async روی Repository Layer برای هر دامنه
    bot/handlers/            همه‌ی دستورات، دسته‌بندی‌شده بر اساس موضوع

⚠️ منبع اصلیِ داده‌های دائمی (Notes/Assistant/AutoPost/Statistics/Clock/
Profile Settings) از این به بعد PostgreSQL است، نه فایل JSON. فایل‌های JSON
قدیمی فقط برای اسکریپت یک‌بارِ migration (scripts/migrate_json_to_postgres.py)
و برای Import/Export دستیِ بکاپ (دستورهای `.پشتیبان تنظیمات` / `.بازیابی`)
استفاده می‌شن.
"""
from bot.logging_config import setup_logging

setup_logging()  # باید قبل از import هر ماژولی که logger می‌سازه صدا زده بشه

import asyncio
import logging

from bot import config
from bot.runtime import (
    client,
    bot_client,
    get_http_session,
    close_http_session,
    set_self_id,
    set_bot_username,
)
from bot.db.bootstrap import load_all_persistent_state
from bot.db.engine import dispose_engine
from bot.plugin_loader import load_all_plugins
from bot.clock import clock_updater
from bot.handlers.autopost import autopost_worker
from bot.handlers.assistant import (
    assistant_status_watcher,
    assistant_session_poller,
    assistant_status_poller,
)
from bot.handlers.daily_digest import daily_digest_worker
from bot.handlers.scheduler import scheduler_worker
from bot.handlers.message_tracker import message_tracker_cleanup_worker
from bot.handlers.price_alert import price_alert_worker
from bot.handlers.recurring import recurring_worker
from bot.handlers.semantic import semantic_index_worker
from bot.handlers.stats import stats_saver
from bot.storage.stats_store import save_stats
from bot.storage.activity_store import flush_message_activity

from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError

# فقط import کردنِ این پکیج کافیه تا همه‌ی دکوریتورهای @client.on ثبت بشن
from bot import handlers  # noqa: F401

logger = logging.getLogger("selfbot.main")


async def connection_watchdog():
    """
    نگهبانِ اتصال: هر ۳۰ ثانیه سلامتِ اتصالِ کلاینت اکانت رو چک می‌کنه.

    چرا لازمه؟ Telethon auto_reconnect داره، ولی اگه قطعی طولانی بشه (یا
    ری‌کانکت خیلی پشتِ سر هم fail بشه)، ممکنه پروسه بدونِ اتصال و بی‌هیچ
    خطایی زنده بمونه — از بیرون یعنی «سلف‌بات غیرفعال شد». این تسک:
      ۱) اگه قطع بود: اول یه ping سبک می‌زنه و دوباره تلاش می‌کنه؛
      ۲) اگه چند دورِ پشتِ هم وصل نشد: پروسه رو با exit(1) می‌بنده تا
         Railway خودش ری‌استارتش کنه (بهترین راهِ بازیابیِ قطعی)؛
      ۳) وضعیت رو برای `.سلامت` ثبت می‌کنه.
    """
    from bot import runtime
    from bot import health
    from telethon import errors as _errors

    fail_streak = 0
    while True:
        try:
            connected = client.is_connected()
            if connected:
                # ping واقعی تا اتصالِ نیمه‌مرده هم لو بره
                try:
                    await asyncio.wait_for(client.get_me(), timeout=20)
                    fail_streak = 0
                    health.update_worker_status("connection_watchdog", "ok")
                except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                    connected = False
                    logger.warning("ping به تلگرام timeout/قطع شد: %r", e)
                except _errors.FloodWaitError as e:
                    # FloodWait یعنی اتصال سالمه؛ فقط صبر
                    logger.warning("watchdog: FloodWait %s ثانیه - صبر", e.seconds)
                    health.update_worker_status("connection_watchdog", "ok")
                    await asyncio.sleep(min(e.seconds, 120))
                    continue
            if not connected:
                fail_streak += 1
                logger.warning(
                    "اتصال قطع است (دورِ متوالی %s) - تلاش برای reconnect...", fail_streak
                )
                health.update_worker_status(
                    "connection_watchdog", "degraded",
                    error=f"disconnected streak={fail_streak}",
                )
                try:
                    await client.connect()
                    if await client.is_user_authorized():
                        me = await client.get_me()
                        logger.info("reconnect موفق - اکانت %s دوباره وصل شد", me.first_name)
                        fail_streak = 0
                        health.update_worker_status("connection_watchdog", "ok")
                    else:
                        logger.error("reconnect شد ولی سشن دیگر authorize نیست!")
                except Exception:
                    logger.exception("reconnect fail شد")
                if fail_streak >= 6:  # ~۶ تلاشِ ناموفق پشتِ هم
                    logger.critical(
                        "اتصال بعد از %s دورِ متوالی برنگشت - پروسه برای ری‌استارتِ "
                        "خودکارِ Railway بسته می‌شه", fail_streak,
                    )
                    # آخرین فرصت: بافرهای آمار/فعالیت را فلاش کن (اگر DB در دسترس است)
                    try:
                        from bot.storage.stats_store import save_stats as _save_stats
                        from bot.storage.activity_store import flush_message_activity as _flush
                        await _save_stats()
                        await _flush()
                    except Exception:
                        logger.exception("فلاشِ آمار قبل از exit شکست خورد (نادیده گرفته شد)")
                    import os as _os
                    _os._exit(1)
        except Exception:
            logger.exception("خطای غیرمنتظره در watchdog اتصال - دورِ بعد ادامه")
        await asyncio.sleep(30)


async def main():
    await get_http_session()  # ساخت ClientSession مشترک قبل از شروع کار

    # باید قبل از استارت شدنِ تسک‌های پس‌زمینه انجام بشه، وگرنه اون تسک‌ها با
    # مقادیر پیش‌فرض (نه آخرین وضعیتِ ذخیره‌شده در PostgreSQL) شروع می‌کنن.
    await load_all_persistent_state()

    # پلاگین‌های اختیاریِ کاربر (پوشه‌ی plugins/ کنارِ bot/) - اگه پوشه وجود
    # نداشته باشه یا خالی باشه، بدونِ خطا رد می‌شه؛ صرفاً یه قابلیتِ اختیاریه.
    loaded_plugins = await load_all_plugins()
    if loaded_plugins:
        logger.info("پلاگین‌های بارگذاری‌شده: %s", ", ".join(loaded_plugins.keys()))

    me = await client.get_me()
    set_self_id(me.id)
    logger.info(
        "سلف‌بات با اکانت %s روشن شد (سشن: %s)",
        me.first_name,
        "StringSession از env" if config.SESSION_STRING else "فایل selfbot_session",
    )

    # تسک‌های پس‌زمینه: reference نگه می‌داریم (GC قادر به جمع‌کردنشان نشود) و
    # یک callback اطمینان می‌دهد اگر هرکدام exception بدهد، در لاگ ببینیم — نه
    # «fire and forget»ِ خاموش که خرابی‌اش نامرئی می‌ماند.
    _bg_tasks: set[asyncio.Task] = set()

    def _bg_done(task: asyncio.Task) -> None:
        _bg_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error(
                "تسکِ پس‌زمینه با خطا متوقف شد: %r", task.exception()
            )

    def _spawn(coro) -> asyncio.Task:
        t = asyncio.create_task(coro)
        _bg_tasks.add(t)
        t.add_done_callback(_bg_done)
        return t

    # بات کمکیِ پنل (اختیاری) - چون تلگرام دکمه‌های شیشه‌ای رو فقط برای
    # پیام‌های ارسالی از طرف یه بات واقعی نمایش می‌ده، دستور «.پنل» پنل
    # دکمه‌ای رو از طریق این بات (نه اکانت شخصی) نشون می‌ده.
    if bot_client is not None:
        await bot_client.start(bot_token=config.BOT_TOKEN)
        bot_me = await bot_client.get_me()
        set_bot_username(bot_me.username)
        logger.info("بات کمکیِ پنل به @%s وصل شد", bot_me.username)
        _spawn(bot_client.run_until_disconnected())
    else:
        logger.warning("BOT_TOKEN تنظیم نشده؛ «.پنل» فقط راهنما می‌ده (بقیه‌ی دستورات عادی کار می‌کنن)")

    for _worker in (
        clock_updater,
        autopost_worker,
        assistant_status_watcher,
        assistant_session_poller,
        assistant_status_poller,
        scheduler_worker,
        daily_digest_worker,
        stats_saver,
        message_tracker_cleanup_worker,
        price_alert_worker,
        recurring_worker,
        semantic_index_worker,
        connection_watchdog,
    ):
        _spawn(_worker())

    # خاموشیِ تمیز: signal handler (خارج از loop) فقط این event را set می‌کند؛
    # خودِ قطعِ تمیز اینجا داخلِ loop انجام می‌شود (run_until_completeِ تودرتو مجاز نیست).
    shutdown_event = asyncio.Event()

    def _request_shutdown():
        loop = client.loop
        loop.call_soon_threadsafe(shutdown_event.set)

    global _shutdown_request_fn
    _shutdown_request_fn = _request_shutdown

    async def _clean_disconnect():
        try:
            await client.disconnect()
        except Exception:
            logger.exception("disconnectِ اکانت شکست خورد")
        if bot_client is not None:
            try:
                await bot_client.disconnect()
            except Exception:
                logger.exception("disconnectِ بات پنل شکست خورد")

    try:
        disconnected_task = asyncio.ensure_future(client.run_until_disconnected())
        shutdown_task = asyncio.ensure_future(shutdown_event.wait())
        done, _pending = await asyncio.wait(
            {disconnected_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if shutdown_event.is_set() and not disconnected_task.done():
            # سیگنال رسید: قطعِ تمیز قبل از خروج
            await _clean_disconnect()
            # ۲ ثانیه فرصت تا تلگرام قطع‌شدنِ سشن را ثبت کند و دیپلویِ جدید
            # «هم‌زمانِ دو IP» حساب نشود (پیشگیری از AuthKeyDuplicated).
            await asyncio.sleep(2)
            disconnected_task.cancel()
            try:
                await disconnected_task
            except (asyncio.CancelledError, Exception):
                logger.debug("disconnected_task بعد از خاموشی بسته شد", exc_info=True)
        elif disconnected_task.done() and disconnected_task.exception():
            raise disconnected_task.exception()
    finally:
        # آخرین شانس برای ذخیره‌ی آماری که هنوز توی بافرِ درون‌حافظه‌ست (هم
        # STATS و هم شمارشِ پیام‌های activity) - وگرنه با هر ری‌دیپلوی روی
        # Railway تا ۶۰ ثانیه‌ی آخر گم می‌شه.
        try:
            await save_stats()
            await flush_message_activity()
        except Exception:
            logger.exception("خطا در ذخیره‌ی نهاییِ آمار هنگام خاموش‌شدن")
        try:
            await _clean_disconnect()
        except Exception:
            logger.exception("خطا در قطعِ نهایی")
        await close_http_session()
        await dispose_engine()


_shutdown_request_fn = None


def _request_shutdown_from_signal():
    """فقط فلگِ خاموشی را داخلِ loop set می‌کند (thread-safe)."""
    if _shutdown_request_fn is not None:
        _shutdown_request_fn()


if __name__ == "__main__":
    import signal

    def _signal_handler(sig, frame):
        """
        خاموشیِ تمیز روی SIGTERM/SIGINT (Railway موقعِ هر ری‌دیپلوی/ری‌استارت
        SIGTERM می‌فرسته). ⚠️ این بخش حیاتیِ جلوگیری از ابطالِ سشن است.
        ⚠️ این هندلر خارج از event loop اجرا می‌شود؛ هیچ await/run_until_complete
        اینجا مجاز نیست — فقط فلگ را thread-safe به loop می‌فرستیم و بقیه‌ی
        خاموشی (disconnect + flush) داخلِ main() انجام می‌شود.
        """
        logger.info("سیگنال %s دریافت شد - درخواستِ خاموشیِ تمیز...", sig)
        try:
            _request_shutdown_from_signal()
        except Exception:
            # حتی اگر setشدنِ فلگ شکست بخورد، پروسه با SIGTERMِ بعدی/پایانِ
            # کانتینر بسته می‌شود؛ ولی برای عیب‌یابی در لاگ می‌آید.
            logger.exception("setشدنِ فلگِ خاموشی شکست خورد")

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        with client:
            client.loop.run_until_complete(main())
    except AuthKeyDuplicatedError:
        # این یعنی SESSION_STRING هم‌زمان از دو IP متفاوت استفاده شده و
        # تلگرام برای همیشه باطلش کرده - ری‌استارتِ ساده حلش نمی‌کنه.
        # به‌جای کرش‌لوپِ سریع (که فشار اضافی روی سرورهای تلگرام می‌ذاره)،
        # یه پیام واضح می‌دیم و چند دقیقه قبل از خروج صبر می‌کنیم تا اگه
        # پلتفرم (مثل Railway) خودکار ری‌استارت می‌کنه، این‌قدر تند تکرار نشه.
        import time

        logger.critical(
            "سشن (SESSION_STRING) باطل شده: هم‌زمان از دو IP/جای مختلف استفاده شده.\n"
            "این خطا با ری‌استارتِ ساده حل نمی‌شه - باید یه سشن جدید بسازی:\n"
            "  ۱) روی سیستم خودت: python generate_session.py\n"
            "  ۲) SESSION_STRING جدید رو جای مقدار قبلی بذار\n"
            "  ۳) مطمئن شو همون سشن هم‌زمان جای دیگه‌ای (لوکال/دیپلوی دیگه) در حال اجرا نیست\n"
            "برای جلوگیری از اسپم لاگ/درخواست به تلگرام، ۳۰۰ ثانیه صبر می‌کنیم و بعد خارج می‌شیم..."
        )
        time.sleep(300)
        raise
