"""
تنظیمات پروژه - همه‌چیز از متغیرهای محیطی (.env) خونده می‌شه.
هیچ ماژول دیگه‌ای مستقیم os.getenv صدا نمی‌زنه؛ همه از اینجا import می‌کنن.
"""
import os
from dotenv import load_dotenv

load_dotenv()

API_ID_RAW = os.getenv("API_ID", "")
API_ID = int(API_ID_RAW) if API_ID_RAW else 0
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

PREFIX = os.getenv("PREFIX", ".")

# --- بات کمکیِ پنل (اختیاری) ---
# چون تلگرام دکمه‌های شیشه‌ای (inline) رو فقط برای پیام‌های ارسالی از طرف یه
# بات واقعی نمایش می‌ده (نه از طرف اکانت شخصی)، دستور «.پنل» از طریق این بات
# جدا (که با توکن BotFather بالا میاد) پنلِ دکمه‌ای رو نشون می‌ده. اگه این
# متغیر خالی بمونه، «.پنل» فقط یه پیام راهنما می‌ده و بقیه‌ی دستورات سلف‌بات
# مثل قبل عادی کار می‌کنن.
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TIMEZONE_OFFSET = float(os.getenv("TIMEZONE_OFFSET", "3.5"))  # پیش‌فرض: تهران (UTC+3:30)
CLOCK_INTERVAL = max(int(os.getenv("CLOCK_INTERVAL", "60")), 30)  # حداقل ۳۰ ثانیه
CLOCK_STYLE_ENV = os.getenv("CLOCK_STYLE", "default")

# --- PostgreSQL (منبع اصلیِ داده‌های دائمی) ---
# فقط از DATABASE_URL خونده می‌شه؛ هیچ Secret/هاست/یوزر/پسورد دیتابیس داخل
# کد نیست. روی Railway وقتی یه Plugin پستگرس اضافه می‌کنی، این متغیر خودکار
# توی سرویس ست می‌شه.
DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))
DB_POOL_RECYCLE_SECONDS = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
DB_ECHO = os.getenv("DB_ECHO", "false").strip().lower() in ("1", "true", "yes", "on")

# --- مسیرهای JSON قدیمی ---
# این فایل‌ها دیگه در زمان اجرا برای ذخیره‌سازی استفاده نمی‌شن (PostgreSQL
# جایگزینشون شده). فقط برای دو مورد نگه داشته شدن:
#   ۱) اسکریپت یک‌بارِ scripts/migrate_json_to_postgres.py که این فایل‌های
#      قدیمی رو می‌خونه و به PostgreSQL منتقل می‌کنه.
#   ۲) سازگاری با مسیر پیش‌فرضِ بکاپ/ایمپورت دستیِ کاربر (دستور پشتیبان/بازیابی).
NOTES_FILE = os.getenv("NOTES_FILE", "notes.json")  # اگه Volume وصل کردی: مثلاً /data/notes.json
AUTOPOST_FILE = os.getenv("AUTOPOST_FILE", "autopost.json")
AUTOPOST_MIN_INTERVAL_MINUTES = 1  # حداقل فاصله مجاز - برای کاهش ریسک اسپم بهتره کمتر از ۵ نذاری
ASSISTANT_FILE = os.getenv("ASSISTANT_FILE", "assistant.json")
FONT_STATE_FILE = os.getenv("FONT_STATE_FILE", "font_state.json")
STATS_FILE = os.getenv("STATS_FILE", "stats.json")

ASSISTANT_ONLINE_THRESHOLD = int(os.getenv("ASSISTANT_ONLINE_THRESHOLD", "180"))  # ثانیه سکوت تا «آفلاین» حساب بشی
ASSISTANT_CHECK_INTERVAL = max(int(os.getenv("ASSISTANT_CHECK_INTERVAL", "30")), 15)  # هر چند ثانیه یک‌بار بازبینیِ محلی (بدون تماس با تلگرام)
ASSISTANT_SCHEDULE_MAX_WINDOWS = max(int(os.getenv("ASSISTANT_SCHEDULE_MAX_WINDOWS", "20")), 1)  # سقفِ تعدادِ بازه‌های زمان‌بندیِ منشی

STATS_SAVE_INTERVAL = 60  # هر چند ثانیه آمار توی PostgreSQL ذخیره بشه

BACKUP_MAX_MESSAGES = 2000
BACKUP_MAX_MEDIA = 50

# --- هوش مصنوعی (اختیاری: .پرسش / .خلاصه / اتصال به .منشی) ---
# یه wrapper سبک روی APIِ چت‌تکمیلیِ سازگار با OpenAI (`/chat/completions`).
# اگه AI_API_KEY خالی بمونه، این قابلیت‌ها فقط یه پیامِ راهنما می‌دن و بقیه‌ی
# دستورات سلف‌بات مثل همیشه عادی کار می‌کنن. AI_API_BASE رو می‌تونی روی هر
# سرویسِ دیگه‌ای (نه فقط OpenAI) که همون فرمتِ درخواست/پاسخ رو داشته باشه ست کنی.
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_BASE = os.getenv("AI_API_BASE", "https://api.openai.com/v1")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
# AI Router (اختیاری): اگر ست شوند، ai_agent بر اساسِ نیت مدل را انتخاب می‌کند
AI_MODEL_FAST = os.getenv("AI_MODEL_FAST", "")
AI_MODEL_CODING = os.getenv("AI_MODEL_CODING", "")
AI_MODEL_REASONING = os.getenv("AI_MODEL_REASONING", "")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "600"))
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))
AI_SUMMARY_MAX_MESSAGES = int(os.getenv("AI_SUMMARY_MAX_MESSAGES", "300"))

# --- جستجوی معنایی در پیام‌های تلگرام (`.پرسش` درباره‌ی گفتگوهای قبلی) ---
# پیام‌ها (به‌صورتِ opt-in، با `.ایندکس روشن`) توی دیتابیسِ خودت ایندکس می‌شن و
# با «embedding» جستجو می‌شن: یعنی «خرید گوشی» با «می‌خوام یه موبایل بخرم» هم
# مچ می‌شه. embedding از endpointِ استانداردِ `/embeddings` (سازگار با OpenAI)
# گرفته می‌شه. پیش‌فرض از همون AI_API_KEY/AI_API_BASE استفاده می‌کنه؛ اگه سرویسِ
# واسطِ تو endpointِ embedding نداره، کلیدِ جدا بده. اگه embedding در دسترس
# نباشه، جستجو خودکار روی حالتِ کلمه‌ای (با نرمال‌سازیِ فارسی) برمی‌گرده.
# (با `or` تا مقدارِ خالی در .env هم به پیش‌فرض برگرده)
AI_EMBED_API_KEY = os.getenv("AI_EMBED_API_KEY") or AI_API_KEY
AI_EMBED_API_BASE = os.getenv("AI_EMBED_API_BASE") or AI_API_BASE
AI_EMBED_MODEL = os.getenv("AI_EMBED_MODEL", "text-embedding-3-small")
# فقط برای مدل‌های خانواده‌ی text-embedding-3 (کوچک‌کردنِ بردار → دیتابیسِ سبک‌تر،
# مثلاً 512)؛ 0 = ارسال نشه. بعد از تغییرِ مدل/ابعاد باید `.ایندکس بازسازی` بزنی.
AI_EMBED_DIMENSIONS = max(int(os.getenv("AI_EMBED_DIMENSIONS", "0") or 0), 0)
# سقفِ تعدادِ پیامِ ایندکس‌شده (قدیمی‌ترین‌ها اول حذف می‌شن) و حداقلِ طولِ پیام
SEMANTIC_MAX_INDEX = max(int(os.getenv("SEMANTIC_MAX_INDEX", "50000")), 1000)
SEMANTIC_MIN_CHARS = max(int(os.getenv("SEMANTIC_MIN_CHARS", "4")), 1)
# حداقلِ شباهتِ کسینوسی برای این‌که یه پیام «مرتبط» حساب بشه (۰ تا ۱)
SEMANTIC_MIN_SCORE = float(os.getenv("SEMANTIC_MIN_SCORE", "0.27"))
# نتیجه‌ی جستجو شاملِ پیام‌های چت‌های دیگه‌ست؛ پیش‌فرض توی «پیام‌های ذخیره‌شده» فرستاده می‌شه
# (تا طرفِ مقابلِ چتی که دستور رو توش زدی نبینه). true = همیشه همون‌جا که دستور زدی نشون بده.
SEMANTIC_REPLY_IN_PLACE = os.getenv("SEMANTIC_REPLY_IN_PLACE", "false").strip().lower() in ("1", "true", "yes", "on")

# برچسبِ مخفیِ «نوشته‌شده با AI» - به انتهای هر پیامی که واقعاً توسطِ
# هوش‌مصنوعی تولید و ارسال می‌شه (پاسخِ `.پرسش`/`.خلاصه`/`.ترجمه‌هوشمند`،
# پاسخِ خودکارِ منشی وقتی `.منشی هوش‌مصنوعی روشن`ه، و ارسالِ `.جواب ارسال`)
# اضافه می‌شه؛ به‌صورتِ اسپویلِ تلگرام (پیش‌فرض محو/جمع‌شده، فقط با تپ دیده
# می‌شه) - نه یه پیشوندِ همیشه‌نمایان - تا هم خودتون بعداً موقعِ مرورِ چت، هم
# طرفِ مقابل (اگه تپ کنه) بتونن تشخیص بدن پیام واقعاً از طرفِ خودِ owner
# نبوده. برای غیرفعال‌کردنِ کامل: AI_TAG_ENABLED=false
AI_TAG_ENABLED = os.getenv("AI_TAG_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
AI_TAG_TEXT = os.getenv("AI_TAG_TEXT", "🤖")

# چند پیامِ آخرِ هر مکالمه (کاربر+منشی، جمعاً) به‌عنوانِ context برای پاسخِ
# هوش‌مصنوعیِ منشی نگه داشته بشه - تا جواب‌ها به همدیگه ربط داشته باشن، نه
# این‌که هر پیام کاملاً مستقل و بدونِ حافظه جواب داده بشه. این حافظه فقط
# درون‌حافظه‌ایه (نه دیتابیس) و با ری‌استارتِ پروسه پاک می‌شه.
ASSISTANT_HISTORY_LIMIT = max(int(os.getenv("ASSISTANT_HISTORY_LIMIT", "10")), 0)

# --- تشخیصِ پیشرفته‌ی آنلاین/آفلاین (لایه‌ی سشن‌های فعال) ---
# علاوه بر سیگنال‌های محلی (پیامِ خروجی/خوندنِ پیام)، هر چند ثانیه یک‌بار
# account.getAuthorizations صدا زده می‌شه و آخرین زمانِ فعالیتِ «هر سشنِ
# اکانت» (گوشی/دسکتاپ/وب — date_active) خونده می‌شه؛ این دقیق‌ترین نشونه‌ی
# حضوره چون هر کاری توی هر دستگاه بکنی (تایپ، خوندن، حتی بازکردنِ اپ)
# date_active اون سشن به‌روز می‌شه. فاصله‌ی پیش‌فرضِ ۱۵ ثانیه (کمترین مقدارِ
# مجاز) بیشترین واکنش‌سرعتی رو می‌ده؛ در صورتِ دیدنِ FloodWait هم backoff
# خودکار داریم و poll موقتاً متوقف می‌مونه تا تلگرام ناراحت نشه.
ASSISTANT_SESSION_POLL_INTERVAL = max(
    int(os.getenv("ASSISTANT_SESSION_POLL_INTERVAL", "15")), 15
)
# سقفِ عمرِ نشونه‌ی سشن (ثانیه): اگه polling از کار افتاد (خطای مکرر/FloodWait
# طولانی)، بعد از این مدت فقط به سیگنال‌های محلی تکیه می‌شه تا وضعیتِ کهنه
# «آنلاین» گول‌مان نزنه.
ASSISTANT_SESSION_MAX_AGE = max(
    int(os.getenv("ASSISTANT_SESSION_MAX_AGE", "300")), 60
)
# آستانه‌ی آنلاین‌بودنِ مخصوصِ لایه‌ی سشن (ثانیه). سشن‌های باز (تلگرام
# دسکتاپ/وب) گاهی فعالیت‌های ریزِ پس‌زمینه ثبت می‌کنند؛ برای همین آستانه‌ی
# این لایه عمداً بزرگ‌تر از آستانه‌ی محلی است (پیش‌فرض: ۳ برابر = ۵۴۰ ثانیه)
# تا «باز‌بودنِ تلگرام بدونِ حضورت» باعث نشه منشی هیچ‌وقت روشن نشه.
# ۰ یا عددِ منفی = خاموش‌کردنِ کاملِ لایه‌ی سشن (فقط سیگنال‌های محلی).
ASSISTANT_SESSION_ONLINE_THRESHOLD = max(
    int(os.getenv("ASSISTANT_SESSION_ONLINE_THRESHOLD", "540")), 0
)
# حالتِ تشخیصِ حضور (ASSISTANT_PRESENCE_MODE):
#   "status"  (پیش‌فرض) — مستقیم وضعیتِ آنلاین/آفلاینِ خودت رو از تلگرام
#              می‌پرسه (همون «آنلاین»/«آخرین بازدید» که توی اپ دیده می‌شه).
#              آنلاین بودی → منشی خاموش؛ به‌محضِ آفلاین‌شدن → روشن. هیچ ربطی
#              به پیامِ فرستادن/خوندن نداره — دقیقاً همون چیزی که اپ نشون می‌ده.
#   "signals" — روشِ قبلی (پیام/خوندن + سشن‌های اکانت)؛ برای شونده‌هایی که
#              حالتِ وضعیتِ پروفایلشون رو مخفی کردن.
ASSISTANT_PRESENCE_MODE = os.getenv("ASSISTANT_PRESENCE_MODE", "status").strip().lower()
if ASSISTANT_PRESENCE_MODE not in ("status", "signals"):
    ASSISTANT_PRESENCE_MODE = "status"
# فاصله‌ی پرسیدنِ وضعیت (ثانیه) در حالتِ status — سبک و امن.
ASSISTANT_STATUS_POLL_INTERVAL = max(
    int(os.getenv("ASSISTANT_STATUS_POLL_INTERVAL", "20")), 10
)
# بعد از این‌که منشی خودش پیام می‌فرسته، تلگرام اکانت رو چند ده ثانیه
# «آنلاین» نشون می‌ده (فعالیتِ سشنِ خودِ بات). برای این‌که منشی با
# «آنلاینِ» جعلیِ حاصل از پیامِ خودش خاموش نشه، به این مدت اعتماد نمی‌کنیم
# (پیش‌فرض ۳۰ ثانیه = عمرِ لیبلِ آنلاینِ تلگرام). اگر بعد از این مدت هنوز
# آنلاین بود، یعنی واقعاً خودتی.
ASSISTANT_REPLY_STATUS_GRACE = max(
    int(os.getenv("ASSISTANT_REPLY_STATUS_GRACE", "30")), 30
)
# grace (ثانیه): برای روشن‌شدنِ منشی (آفلاین‌شدنت) باید «حداقل» این مدت از
# آخرین سیگنالِ هر دو منبع گذشته باشه — ضدِ flicker (مثلاً خوندنِ سریعِ یه
# پیام نباید منشی رو روشن کنه؛ تایمرِ سکوت هم دوباره از صفر شروع می‌شه).
ASSISTANT_OFFLINE_GRACE = max(
    int(os.getenv("ASSISTANT_OFFLINE_GRACE", "60")), 0
)

# --- خلاصه‌ی روزانه (`.خلاصه‌روز`) ---
# ساعت/دقیقه‌ی پیش‌فرضِ ارسالِ خودکارِ خلاصه‌ی هر شب (به‌وقتِ محلی، طبقِ
# TIMEZONE_OFFSET) - با `.خلاصه‌روز زمان HH:MM` هم از داخلِ ربات قابلِ تغییره.
DAILY_DIGEST_DEFAULT_HOUR = max(min(int(os.getenv("DAILY_DIGEST_DEFAULT_HOUR", "23")), 23), 0)
DAILY_DIGEST_DEFAULT_MINUTE = max(min(int(os.getenv("DAILY_DIGEST_DEFAULT_MINUTE", "0")), 59), 0)
# سقفِ تعدادِ پیام‌های بررسی‌شده به‌ازای هر چت (برای جلوگیری از هزینه/تایم‌اوتِ AI)
DAILY_DIGEST_MAX_MESSAGES_PER_CHAT = int(os.getenv("DAILY_DIGEST_MAX_MESSAGES_PER_CHAT", "150"))
# سقفِ تعدادِ چت‌هایی که توی حالتِ «کلی» یک‌جا پردازش می‌شن (برای گروه/کانال/پیویِ زیاد)
DAILY_DIGEST_MAX_CHATS = int(os.getenv("DAILY_DIGEST_MAX_CHATS", "40"))

# --- صوت و متن (اختیاری: .رونویسی / .متن‌به‌صوت) ---
# پیش‌فرض: از همون AI_API_KEY/AI_API_BASE بالا استفاده می‌کنن. ولی چون خیلی
# از سرویس‌های واسط/proxy (مثلاً OpenRouter و مشابه‌ها) endpointهای صوتی
# (/audio/speech ، /audio/transcriptions) رو پیاده‌سازی نمی‌کنن - حتی اگه
# برای چت (/chat/completions) کار کنن - این دو متغیرِ جدا رو هم اضافه
# کردیم: اگه ست بشن، فقط بخشِ صوت (.رونویسی/.متن‌به‌صوت) از این‌ها استفاده
# می‌کنه (مثلاً می‌تونی برای AI_API_BASE یه proxy ارزون بذاری ولی برای صوت
# یه کلیدِ واقعیِ OpenAI اینجا بدی). اگه ست نشن، دقیقاً مثلِ قبل از همون
# AI_API_KEY/AI_API_BASE بالا استفاده می‌کنن.
AI_AUDIO_API_KEY = os.getenv("AI_AUDIO_API_KEY", AI_API_KEY)
AI_AUDIO_API_BASE = os.getenv("AI_AUDIO_API_BASE", AI_API_BASE)

AI_STT_MODEL = os.getenv("AI_STT_MODEL", "whisper-1")
AI_TTS_MODEL = os.getenv("AI_TTS_MODEL", "tts-1")
AI_TTS_VOICE = os.getenv("AI_TTS_VOICE", "alloy")
AI_TTS_TIMEOUT = int(os.getenv("AI_TTS_TIMEOUT", "60"))

# --- صوت و متن، نسخه‌ی رایگان/بدونِ AI (bot/local_speech.py) ---
# پیش‌فرض: رونویسی از موتورِ رایگانِ گوگل، متن‌به‌صوت از edge-tts - هیچ‌کدوم
# نیاز به AI_API_KEY ندارن. اگه می‌خوای زبان/صدا رو عوض کنی:
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "fa-IR")
TTS_VOICE = os.getenv("TTS_VOICE", "fa-IR-FaridNeural")

# --- مدیریت گروه پیشرفته: فیلترِ پورن/اسپم (.فیلترپورن / .فیلتراسپم) ---
# فیلترِ پورن از همون سرویسِ هوش‌مصنوعیِ بالا (AI_API_KEY/AI_MODEL) برای
# تحلیلِ تصویر استفاده می‌کنه - پس AI_MODEL باید از ورودیِ تصویر (Vision)
# پشتیبانی کنه (پیش‌فرضِ بالا، gpt-4o-mini، این قابلیت رو داره). اگه
# AI_API_KEY ست نباشه یا مدل تصویر رو پشتیبانی نکنه، فیلترِ پورن fail-open
# می‌کنه (یعنی به‌جای حذفِ اشتباهیِ عکس‌های سالم، کاری نمی‌کنه).
GROUP_PORN_FILTER_MAX_BYTES = int(
    os.getenv("GROUP_PORN_FILTER_MAX_BYTES", str(8 * 1024 * 1024))
)  # عکس‌های بزرگ‌تر از این چک نمی‌شن (برای جلوگیری از دانلودهای سنگین/کند)
# چند بار (مجموع) برای هر عکس از مدل بپرسیم اگه پاسخ خالی/مبهم بود - بعضی
# سرویس‌ها گاهی خالی جواب می‌دهن و تلاشِ بعدی درست تشخیص می‌ده.
GROUP_PORN_FILTER_RETRIES = int(os.getenv("GROUP_PORN_FILTER_RETRIES", "3"))

# فیلترِ اسپم کاملاً محلیه (بدونِ نیاز به AI): تشخیصِ فلادِ پیام (تعداد زیاد
# توی یه بازه‌ی کوتاه) و تکرارِ عینِ یه متن از طرفِ یک نفر.
GROUP_SPAM_WINDOW_SECONDS = int(os.getenv("GROUP_SPAM_WINDOW_SECONDS", "10"))
GROUP_SPAM_MAX_MESSAGES = int(os.getenv("GROUP_SPAM_MAX_MESSAGES", "6"))
GROUP_SPAM_DUPLICATE_THRESHOLD = int(os.getenv("GROUP_SPAM_DUPLICATE_THRESHOLD", "3"))
GROUP_SPAM_WARN_COOLDOWN_SECONDS = int(os.getenv("GROUP_SPAM_WARN_COOLDOWN_SECONDS", "20"))

# --- کپی کانال (`.کپی‌کانال`) ---
# فوروارد دسته‌ایِ همه‌ی پست‌های یک کانال به کانالِ دیگه، با رعایتِ محدودیت‌های
# تلگرام. مقادیر پیش‌فرض عمداً محافظه‌کارانه‌ان تا ریسکِ FloodWait/محدودشدنِ
# اکانت کم باشه.
#   CHANNEL_COPY_BATCH_SIZE    : تعدادِ پیام در هر درخواستِ فوروارد (سقفِ تلگرام ۱۰۰)
#   CHANNEL_COPY_DELAY_SECONDS : مکثِ بینِ دو درخواستِ فوروارد (ثانیه، حداقل ۳)
#   CHANNEL_COPY_DAILY_LIMIT   : سقفِ پیامِ کپی‌شده در هر ۲۴ ساعت (پیش‌فرض ۰ = بدونِ سقف)
CHANNEL_COPY_BATCH_SIZE = max(min(int(os.getenv("CHANNEL_COPY_BATCH_SIZE", "20")), 100), 1)
CHANNEL_COPY_DELAY_SECONDS = max(float(os.getenv("CHANNEL_COPY_DELAY_SECONDS", "8")), 3.0)
CHANNEL_COPY_DAILY_LIMIT = max(int(os.getenv("CHANNEL_COPY_DAILY_LIMIT", "0")), 0)
# فاصله‌ی چک‌کردنِ پیام‌هایِ تازه در حالتِ «از این به بعد» (ثانیه، حداقل ۳۰)
CHANNEL_COPY_WATCH_SECONDS = max(float(os.getenv("CHANNEL_COPY_WATCH_SECONDS", "60")), 30.0)
