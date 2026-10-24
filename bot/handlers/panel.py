"""۱۴) پنل: نمایش گرافیکی/دکمه‌ای دستورات (.پنل)"""
from telethon import events, Button

from .. import runtime
from ..config import PREFIX
from ..runtime import client
from ..utils import pat

CB_PREFIX = "p:"


def _cb(action: str) -> bytes:
    return f"{CB_PREFIX}{action}".encode()


def _divider() -> str:
    return "────────────────────────"


# هر بخش: کلید (برای callback)، ایموجی، عنوان، و لیست دستورات (دقیقاً هماهنگ با راهنما).
CATEGORIES = [
    {
        "key": "general",
        "emoji": "🧩",
        "title": "عمومی",
        "commands": [
            f"`{PREFIX}پینگ` — تست پینگ",
            f"`{PREFIX}فعال` — وضعیت بات",
            f"`{PREFIX}آیدی` — آیدی چت/کاربر/پیام",
            f"`{PREFIX}اطلاعات` — اطلاعات کاربر (ریپلای اختیاری)",
        ],
    },
    {
        "key": "tools",
        "emoji": "🛠",
        "title": "ابزار",
        "commands": [
            f"`{PREFIX}تقویم` — تاریخِ امروز شمسی + میلادی",
            f"`{PREFIX}تبدیل‌تاریخ` `<1403/05/01>` — تبدیلِ شمسی↔میلادی",
            f"`{PREFIX}دیکشنری` `<کلمه>` — معنیِ انگلیسی↔فارسی",
            f"`{PREFIX}حساب` `<عبارت>` — ماشین‌حساب (sqrt, sin, log, pi, ...)",
            f"`{PREFIX}کیوآر` `<متن>` — ساخت کیو‌آر کد",
            f"`{PREFIX}کوتاه` `<لینک>` — کوتاه‌کردن لینک",
            f"`{PREFIX}هوا` `<شهر>` — آب‌وهوا",
            f"`{PREFIX}ترجمه` `<زبان> <متن>` — ترجمه",
            f"`{PREFIX}گوگل` `<عبارت>` — جستجوی گوگل",
            f"`{PREFIX}رمزعبور` `<طول اختیاری>` — ساخت رمز عبور تصادفی",
            f"`{PREFIX}هش` `<الگوریتم اختیاری> <متن>` — md5/sha1/sha256/sha512 (یا ریپلای)",
            f"`{PREFIX}بیس64` `انکد/دیکد <متن>` — تبدیل بیس۶۴ (یا ریپلای)",
            f"`{PREFIX}نویسه‌شمار` `<متن>` — شمارش حروف/کلمات/خط (یا ریپلای)",
            f"`{PREFIX}ارز` `<عدد> <از> <به>` — تبدیل نرخ ارز",
            f"`{PREFIX}قیمت` — قیمت لحظه‌ای دلار/یورو/طلا/سکه به ریال (tgju.org)",
            f"`{PREFIX}قیمت` `<طلا/ارز/سکه>` — فقط یه بخش",
            f"`{PREFIX}قیمت` `<اسم کالا>` — جستجوی یه قلم خاص (مثلاً `{PREFIX}قیمت دلار`)",
            f"`{PREFIX}هشدارقیمت افزودن` `<آیتم> <بالا/پایین> <عدد>` — اطلاع‌دادنِ خودکار وقتی قیمت به حدی برسه",
            f"`{PREFIX}هشدارقیمت لیست/حذف/پاک`",
            f"`{PREFIX}مبدل` `<عدد> <واحد مبدا> <واحد مقصد>` — تبدیلِ واحد (طول/وزن/دما/حجم/سرعت)",
        ],
    },
    {
        "key": "notes",
        "emoji": "🗒",
        "title": "یادداشت",
        "commands": [
            f"`{PREFIX}یادداشت` `<کلید> <متن>` — ذخیره یادداشت",
            f"`{PREFIX}یادداشت‌ها` — لیست یادداشت‌ها",
            f"`{PREFIX}نمایش‌یادداشت` `<کلید>` — نمایش یادداشت",
            f"`{PREFIX}حذف‌یادداشت` `<کلید>` — حذف یادداشت",
        ],
    },
    {
        "key": "msg",
        "emoji": "🧹",
        "title": "مدیریت پیام",
        "commands": [
            f"`{PREFIX}اسپویل` `<متن>` — ارسالِ اسپویل",
            f"`{PREFIX}حذف` — حذف پیام ریپلای‌شده",
            f"`{PREFIX}پاکسازی` `<عدد>` — حذف چند پیام آخر (یا ریپلای)",
            f"`{PREFIX}سنجاق` / `{PREFIX}برداشتن‌سنجاق` — پین/آنپین پیام ریپلای‌شده",
        ],
    },
    {
        "key": "fun",
        "emoji": "🎉",
        "title": "سرگرمی",
        "commands": [
            f"`{PREFIX}فرار` — اتاقِ فرارِ متنیِ داستانی (۲۰ سناریو، معما، کوله، Boss، رکورد، روزانه)",
            f"`{PREFIX}تایپ‌زنده` `<متن>` — افکت تایپ زنده",
            f"`{PREFIX}پیش‌تایپ` `<متن>` — شبیه‌سازی تایپ قبل از ارسال",
            f"`{PREFIX}معکوس` `<متن>` — معکوس کردن متن",
            f"`{PREFIX}طنز` `<متن>` — حروف بزرگ‌وکوچکِ متناوب",
            f"`{PREFIX}تاس` `<۱ تا ۶>` — انداختن تاس واقعی",
            f"`{PREFIX}شیرخط` — شیر یا خط",
            f"`{PREFIX}تصادفی` `<min> <max>` — عدد تصادفی",
            f"`{PREFIX}انتخاب` `<گزینه۱, گزینه۲, ...>` — انتخاب تصادفی",
            f"`{PREFIX}سنگ‌کاغذقیچی` `<سنگ/کاغذ/قیچی>` — بازی با بات",
            f"`{PREFIX}حدس شروع` `<سقف اختیاری>` — شروع بازیِ حدسِ عدد",
            f"`{PREFIX}حدس` `<عدد>` — حدس‌زدن توی بازیِ فعال",
            f"`{PREFIX}حدس لغو` — لغو بازیِ فعال",
            f"`{PREFIX}اسلات` — ماشین اسلات",
            f"`{PREFIX}جادوگر` `<سوال>` — پاسخ تصادفیِ توپ جادویی",
            f"`{PREFIX}عشق‌سنج` `<اسم۱> و <اسم۲>` — عشق‌سنجِ شوخی",
            f"`{PREFIX}این‌یا‌اون` — یه سوالِ «این یا اون» تصادفی",
            f"`{PREFIX}کوییز` — سوالِ عمومیِ چهارگزینه‌ای (Open Trivia DB)",
            f"`{PREFIX}کوییز` `<۱ تا ۴>` — جواب‌دادن به سوالِ فعال",
            f"`{PREFIX}فال` — فالِ حافظِ تصادفی با تفسیر",
            f"`{PREFIX}کلمه‌ساز` `شروع` — بازیِ زنجیره‌کلمات",
            f"`{PREFIX}حدس‌کلمه` `شروع` — حدسِ کلمه‌ی پنهان (۶ اشتباه)",
            f"`{PREFIX}مار‌پله شروع` — صفحه‌ی ۱۰×۱۰، ۱۰۰ خانه، تاسِ واقعی؛ `{PREFIX}مار‌پله با‌ربات` هم بازیِ تکی",
            f"`{PREFIX}حافظه` `شروع` — بازیِ حافظه‌ی اعداد",
        ],
    },
    {
        "key": "font",
        "emoji": "🔤",
        "title": "فونت پیام",
        "commands": [
            f"`{PREFIX}قلم فهرست` — لیست فونت‌های موجود",
            f"`{PREFIX}قلم` `<نام> <متن>` — تبدیل یه‌بارِ متن",
            f"`{PREFIX}قلم تنظیم` `<نام>` — فونت پیش‌فرض خودکار",
            f"`{PREFIX}قلم روشن/خاموش` — اعمال خودکار فونت روی پیام‌ها",
            f"`{PREFIX}قلم وضعیت` — وضعیت فونت خودکار",
        ],
    },
    {
        "key": "profile",
        "emoji": "👤",
        "title": "پروفایل",
        "commands": [
            f"`{PREFIX}نشست‌ها` — دستگاه‌های لاگین‌شده + خروجِ اجباری",
            f"`{PREFIX}بیو` `<متن>` — تغییر بیو",
            f"`{PREFIX}نام` `<متن>` — تغییر نام پایه",
            f"`{PREFIX}عکس` — تغییر عکس پروفایل (ریپلای روی عکس)",
            f"`{PREFIX}ساعت روشن/خاموش` — ساعت زنده در نام",
            f"`{PREFIX}مدل‌ساعت` — لیست مدل‌های ساعت",
            f"`{PREFIX}مدل‌ساعت` `<نام>/بعدی` — تغییر مدل ساعت",
            f"`{PREFIX}کاربر` — پروفایلِ داخلیِ کاربر (ریپلای/`<شناسه>`؛ بدونِ آرگومان = خودت)",
            f"`{PREFIX}برچسب` `<شناسه> <برچسب>` — افزودنِ تگ (حذف: `برچسب حذف`)",
            f"`{PREFIX}یادداشت‌کاربر` `<شناسه> <متن>` — یادداشتِ خصوصی روی یه کاربر",
        ],
    },
    {
        "key": "assistant",
        "emoji": "🤖",
        "title": "منشی چت",
        "commands": [
            f"`{PREFIX}منشی روشن/خاموش` — روشن/خاموش دستی",
            f"`{PREFIX}منشی خودکار` — تشخیص خودکار دولایه (فعالیت + سشن‌های اکانت)",
            f"`{PREFIX}منشی وضعیت` — نمایش وضعیت منشی",
            f"`{PREFIX}منشی متن` `<متن>` — تنظیم پیام پاسخ",
            f"`{PREFIX}منشی تأخیر` `<ثانیه>` — تنظیم تأخیر",
            f"`{PREFIX}منشی حالت` `<خودکار/منشن/پیوی/گروه‌ها>`",
            f"`{PREFIX}منشی مستثنی` / `{PREFIX}منشی شامل` — چت فعلی",
            f"`{PREFIX}منشی پاک` — حذف لیست چت‌ها",
            f"`{PREFIX}منشی زمان‌بندی` — نمایش لیستِ بازه‌های ساعتیِ «حتماً روشن» (مثل خواب/ساعتِ کاری)",
            f"`{PREFIX}منشی زمان‌بندی افزودن` `<شروع> <پایان> [برچسب]` — مثلاً `23:00 08:00 خواب`",
            f"`{PREFIX}منشی زمان‌بندی حذف` `<شماره>` — حذفِ یه بازه",
            f"`{PREFIX}منشی زمان‌بندی پاک` — حذفِ همه‌ی بازه‌ها",
            f"`{PREFIX}منشی زمان‌بندی روشن/خاموش` — کلِ لایه‌ی زمان‌بندی (بدونِ پاک‌کردنِ بازه‌ها)",
        ],
    },
    {
        "key": "admin",
        "emoji": "👮",
        "title": "مدیریت گروه",
        "commands": [
            f"`{PREFIX}اطلاعات‌گروه` — اطلاعاتِ گروهِ فعلی",
            f"`{PREFIX}اخراج` / `{PREFIX}مسدود` / `{PREFIX}رفع‌مسدود` — ریپلای روی کاربر",
            f"`{PREFIX}ارتقا` / `{PREFIX}تنزل` — ریپلای روی کاربر",
            f"`{PREFIX}بی‌صدا` `<دقیقه اختیاری>` / `{PREFIX}رفع‌سکوت`",
            f"`{PREFIX}ادمین‌ها` — لیست ادمین‌های گروه",
            f"`{PREFIX}لینک‌گروه` — لینک دعوت گروه",
            f"`{PREFIX}قفل‌گروه` / `{PREFIX}بازکردن‌گروه`",
            f"`{PREFIX}فیلترلینک روشن/خاموش/وضعیت` — حذف خودکار پیام‌های لینک‌دار از غیرادمین‌ها",
            f"`{PREFIX}خوش‌آمد روشن/خاموش/متن` `<متن>` — خوش‌آمدگویی خودکار برای عضو جدید",
            f"`{PREFIX}فیلترپورن روشن/خاموش/وضعیت` — حذفِ خودکارِ عکسِ نامناسب با AI (نیازمندِ `AI_API_KEY` با مدلِ Vision)",
            f"`{PREFIX}قفل‌رسانه` `<نوع> روشن/خاموش` — قفلِ استیکر/ویدیو/صدا/وویس/گیف/عکس/بازی/نظرسنجی برای غیرادمین‌ها",
            f"`{PREFIX}فیلترپورن تست` — ریپلای روی عکس؛ پاسخِ خامِ AI یا خطای دقیق برای عیب‌یابیِ سریع",
            f"`{PREFIX}فیلتراسپم روشن/خاموش/وضعیت` — حذفِ خودکارِ فلاد/تکرارِ پیام از غیرادمین‌ها (بدونِ نیاز به AI)",
            f"`{PREFIX}فیلترفحش روشن/خاموش/وضعیت` — حذفِ خودکارِ پیامِ حاویِ کلماتِ رکیک از غیرادمین‌ها (لیستِ داخلی، بدونِ نیاز به AI)",
            f"`{PREFIX}فیلترکلمه` `افزودن/حذف/لیست/پاک` — فیلترِ کلماتِ ممنوعه‌ی سفارشی (حذف/اخطار/بن)",
            f"`{PREFIX}اخطار` `افزودن/حذف/پاک/لیست/تنظیمات` — سیستمِ هشدارِ تدریجی با اقدامِ خودکار (mute/kick/ban)؛ افزودن/حذف/پاک با ریپلای هم کار می‌کنه",
            f"`{PREFIX}گزارش` `امروز/هفته/<تعداد روز>` — گزارشِ فعالیتِ گروه (پیام/هشدار/حذف/عضوِ جدید/خارج‌شده)",
            f"`{PREFIX}برچسب‌همه` `<متن اختیاری>` — تگ‌کردنِ همه‌ی اعضا (با احتیاط، ریسکِ اسپم)",
            "⚠️ فقط جایی که خودتون ادمین هستید",
        ],
    },
    {
        "key": "poll",
        "emoji": "📊",
        "title": "نظرسنجی",
        "commands": [
            f"`{PREFIX}نظرسنجی` `<سوال> | گزینه۱ | گزینه۲ | ...` — ایجادِ نظرسنجیِ جدید (حداکثر ۱۰ گزینه)",
            f"`{PREFIX}نظرسنجی بستن` — بستنِ نظرسنجیِ جاری (با ریپلای)",
            f"`{PREFIX}نظرسنجی جمع‌بندی` — جمع‌بندیِ نتایجِ نظرسنجی (با ریپلای)",
        ],
    },
    {
        "key": "backup",
        "emoji": "💾",
        "title": "بکاپ‌گیری",
        "commands": [
            f"`{PREFIX}پشتیبان` `<عدد>` — بکاپ متنی به Saved Messages",
            f"`{PREFIX}پشتیبان json` `<عدد>` — همون، خروجی JSON",
            f"`{PREFIX}پشتیبان رسانه` `<عدد>` — دانلود/فوروارد رسانه",
            f"`{PREFIX}پشتیبان چت‌ها` — بکاپ لیست همه‌ی چت‌ها",
            f"`{PREFIX}پشتیبان تنظیمات` — بکاپ کامل تنظیمات بات",
            f"`{PREFIX}بازیابی` — ریپلای روی فایل بکاپِ تنظیمات",
        ],
    },
    {
        "key": "settings_center",
        "emoji": "⚙️",
        "title": "تنظیماتِ یکپارچه",
        "commands": [
            f"`{PREFIX}تنظیمات` — وضعیتِ زنده‌ی منشی/AI/زمان‌بند/ارسالِ‌خودکار/فونت/آمار/اعلان",
            f"`{PREFIX}تنظیمات تنظیم` `<key> <true|false>` — روشن/خاموش‌کردنِ مستقیمِ همون بخش",
            "🛡 محافظِ گروه اینجا نیست؛ سراسری نیست، هر گروه جدا تنظیم می‌شه",
        ],
    },
    {
        "key": "automation",
        "emoji": "⚡",
        "title": "موتورِ اتوماسیون",
        "commands": [
            f"`{PREFIX}اتوماسیون` — لیستِ قوانین",
            f"`{PREFIX}اتوماسیون جدید` `<نام> <رویداد> <عملیات> <مقدار>` — فعلاً فقط رویدادِ message وصله",
            f"`{PREFIX}اتوماسیون فعال/غیرفعال/حذف/اطلاعات` `<id>`",
        ],
    },
    {
        "key": "notifications",
        "emoji": "🔔",
        "title": "مرکزِ اعلان‌ها",
        "commands": [
            f"`{PREFIX}اعلان` — لیستِ قوانینِ اعلان",
            f"`{PREFIX}اعلان جدید` `<نام> <نوع> <مقدار> <عملیات>` — نوعِ time فعلاً پشتیبانی نمی‌شه",
            f"`{PREFIX}اعلان فعال/غیرفعال/حذف/اطلاعات` `<id>`",
        ],
    },
    {
        "key": "inbox",
        "emoji": "📥",
        "title": "اینباکسِ داخلی",
        "commands": [
            f"`{PREFIX}ذخیره` — با ریپلای روی یه پیام، ذخیره‌ش می‌کنه (اختیاری: مهم/فوری)",
            f"`{PREFIX}اینباکس` — نمایش (یا `مهم`/`خوانده`/`نخوانده`/`پاک <id>`)",
            f"`{PREFIX}اینباکس پاسخ` — منتظرِ پاسخ (ترِیاجِ اتوپایلوت)",
            f"`{PREFIX}اینباکس خلاصه` — 🧠 خلاصه‌ی هوشمند با AI",
        ],
    },
    {
        "key": "ai_memory",
        "emoji": "🧠",
        "title": "حافظه‌ی AI",
        "commands": [
            f"`{PREFIX}حافظه` — آمارِ حافظه",
            f"`{PREFIX}حافظه افزودن/جستجو/حذف/لیست/پاک` — مدیریتِ آیتم‌های حافظه",
            f"`{PREFIX}حافظه وضعیت` — حافظه‌ی هوشمند + idها",
            f"`{PREFIX}حافظه یادبگیر` `<متن>` — ذخیره‌ی ساختاریافته با AI (👤📌📝💡🔗)",
            f"`{PREFIX}دانش افزودن` `<عنوان>` `<متن|ریپلای>` — 📚 Knowledge Base",
            f"`{PREFIX}دانش لیست/جستجو/حذف` — پرونده‌های دانش (AI از آن‌ها جواب می‌دهد)",
            f"`{PREFIX}حافظه ازپیام` — یادگیری از پیامِ ریپلای‌شده",
            "🧠 خاطراتِ مرتبط خودکار در `.پرسش` و منشیِ AI تزریق می‌شوند",
        ],
    },
    {
        "key": "global_search",
        "emoji": "🔍",
        "title": "جستجوی جهانی",
        "commands": [
            f"`{PREFIX}جستجو` `<عبارت>` — یادداشت‌ها، حافظه‌ی AI، پروفایل‌ها، اینباکس، زمان‌بندی + پیام‌های تلگرام + کانال/گروه/کاربرِ کلِ تلگرام",
            f"`{PREFIX}جستجو هوشمند` `<عبارت>` — 🧠 همون + خلاصه/دسته‌بندیِ AI",
        ],
    },
    {
        "key": "smart_reply",
        "emoji": "💬",
        "title": "پاسخِ هوشمند",
        "commands": [
            f"`{PREFIX}جواب` `<رسمی|دوستانه|طنز|کوتاه|حرفه‌ای>` — با ریپلای، پیش‌نویسِ پاسخ با AI",
            f"`{PREFIX}سبک` `<نام>` — 🎨 ذخیره‌ی سبکِ پیش‌فرض",
            f"`{PREFIX}شخصیت` `<حرفه‌ای|دوستانه|کوتاه|برنامه‌نویس|طنز|سفارشی>` — 🎭 سبکِ همه‌ی AIها",
            "⚠️ نیازمندِ `AI_API_KEY`",
        ],
    },
    {
        "key": "health",
        "emoji": "🩺",
        "title": "سلامتِ سیستم",
        "commands": [
            f"`{PREFIX}سلامت` — وضعیتِ دیتابیس و ورکرهای پس‌زمینه + uptime",
        ],
    },
    {
        "key": "message_tracker",
        "emoji": "🕵️",
        "title": "ردیابِ ویرایش/حذف",
        "commands": [
            f"`{PREFIX}ردیاب` — وضعیت + راهنما",
            f"`{PREFIX}ردیاب روشن/خاموش`",
            f"`{PREFIX}ردیاب تنظیم/افزودن/حذف` `<chat_id>` — کانالِ مقصدِ گزارش‌ها (بدونِ آرگومان = همون چتی که توش دستور می‌زنی)",
            f"`{PREFIX}ردیاب پاک` — کلِ لیستِ مقصدها رو خالی می‌کنه",
            "⚠️ فقط پیام‌های *ورودی* (نه خودِ owner) ردیابی می‌شن؛ کشِ پیام‌ها فقط توی حافظه‌ست (با ری‌استارت پاک می‌شه)",
        ],
    },
    {
        "key": "plugins_cmd",
        "emoji": "🧩",
        "title": "پلاگین‌ها",
        "commands": [
            f"`{PREFIX}پلاگین` — لیستِ پلاگین‌های فعال (داخلی + نصب‌شده)",
            f"`{PREFIX}پلاگین نصب` `<لینکِ فایلِ .py در گیت‌هاب>` — نصب و بارگذاریِ آنی، بدونِ ری‌استارت",
            f"`{PREFIX}پلاگین حذف` `<نام>` — حذفِ پلاگینِ نصب‌شده",
            f"`{PREFIX}پلاگین reload` `<نام>` — Unload/Load دوباره، بدونِ ری‌استارتِ کلِ بات",
            f"`{PREFIX}پلاگین اطلاعات` `<نام>` — توضیح/دستورها/هندلرها/config",
            f"`{PREFIX}پلاگین فعال/غیرفعال` `<نام>` — خاموش/روشنِ پایدار",
            f"`{PREFIX}پلاگین بروزرسانی` `<نام>` — نصبِ مجدد از URLِ اصلی",
            "⚠️ پلاگین با سطحِ دسترسیِ خودِ اکانت اجرا می‌شه؛ فقط کدِ مطمئن نصب کن",
        ],
    },
    {
        "key": "autopost",
        "emoji": "📤",
        "title": "ارسال خودکار",
        "commands": [
            f"`{PREFIX}ارسال‌خودکار` — نمایش وضعیت کامل",
            f"`{PREFIX}ارسال‌خودکار روشن/خاموش`",
            f"`{PREFIX}ارسال‌خودکار فاصله` `<دقیقه>`",
            f"`{PREFIX}ارسال‌خودکار متن` `<متن>` (یا ریپلای)",
            f"`{PREFIX}ارسال‌خودکار افزودن/حذف` — گروه فعلی",
            f"`{PREFIX}ارسال‌خودکار پاک` — پاک‌کردن مقصدها",
            f"`{PREFIX}ارسال‌خودکار فوری` — تست فوری",
        ],
    },
    {
        "key": "scheduler",
        "emoji": "⏰",
        "title": "زمان‌بندی و یادآوری",
        "commands": [
            f"`{PREFIX}تکرار` `هر <فاصله> <متن>` — ارسالِ تکرارشونده (هر 30دقیقه / روزانه 08:00)",
            f"`{PREFIX}تکرار` `لیست/توقف/ادامه/حذف` — مدیریتِ تکرارها",
            f"`{PREFIX}زمان‌بند` `<زمان> <متن>` — ارسال متن سرِ وقت توی همین چت (یا ریپلای)",
            f"`{PREFIX}زمان‌بند لیست` — پیام‌های زمان‌بندی‌شده‌ی این چت",
            f"`{PREFIX}زمان‌بند لغو` `<شناسه>` — لغوِ یک زمان‌بندی",
            f"`{PREFIX}یادآوری` `<زمان> <متن>` — یادآوری سرِ وقت به Saved Messages (یا ریپلای)",
            f"`{PREFIX}یادآوری لیست` — یادآوری‌های ثبت‌شده",
            f"`{PREFIX}یادآوری لغو` `<شناسه>` — لغوِ یک یادآوری",
            f"`{PREFIX}یادآوری` `<متنِ طبیعی>` — 🧠 هوشمند: «فردا ساعت ۸ جلسه برو»",
            "فرمتِ زمان: نسبی (`10m`/`2h`/`1d`/`10دقیقه`/`2ساعت`)، ساعتِ امروز/فردا (`14:30`)، یا کامل (`2026-08-25 14:30`)",
            f"`{PREFIX}کار` — 🔥 کارهای باز (Task Manager)",
            f"`{PREFIX}کار افزودن` `<متن>` `-- فردا 18:00` — کارِ جدید با ددلاینِ اختیاری",
            f"`{PREFIX}کارهای امروز` / `{PREFIX}کارهای عقب` / `{PREFIX}کار انجام` `<id>`",
            f"`{PREFIX}اتوپایل روشن/خاموش` — 🤖 تحلیلِ خودکارِ پیام‌های خصوصی (مهم/یادآوری/نیاز به پاسخ)",
            f"`{PREFIX}اتوپایل مستثنی` — بی‌خیالِ چتِ فعلی (toggle)",
        ],
    },
    {
        "key": "channel_copy",
        "emoji": "📦",
        "title": "کپی کانال",
        "commands": [
            f"`{PREFIX}کپی‌کانال شروع` `@مبدا @مقصد` — فورواردِ همه‌ی پست‌ها (بدونِ برچسب)",
            f"`{PREFIX}کپی‌کانال شروع` `@مقصد` + **ریپلای** روی پستِ کانالِ مبدأ — بدونِ آدرسِ مبدأ",
            f"`{PREFIX}کپی‌کانال شروع` `@مبدا @مقصد از 1200` — از پیامِ خاص",
            f"`{PREFIX}کپی‌کانال شروع` `@مبدا @مقصد از 1403/05/01` — از یک تاریخ (شمسی/میلادی)",
            f"`{PREFIX}کپی‌کانال شروع` `@مبدا @مقصد از 1403/05/01 ساعت 10:30` — با ساعتِ دقیق",
            f"`{PREFIX}کپی‌کانال شروع` `@مبدا @مقصد از امروز` — امروز/دیروز/پریروز",
            f"`{PREFIX}کپی‌کانال شروع` `@مبدا @مقصد ازاین‌بعد` — از این به بعد + هر پستِ تازه خودکار 👀",
            f"`{PREFIX}کپی‌کانال شروع` `@مبدا1,@مبدا2 @مقصد` — چند کانال هم‌زمان",
            f"`{PREFIX}کپی‌کانال شروع` `پوشه:3 @مقصد` — همه‌ی کانال‌های یک پوشه",
            f"`{PREFIX}کپی‌کانال شروع` `@مبدا @مقصد با‌نام` — با برچسبِ Forwarded",
        ],
    },
    {
        "key": "channel_copy_private",
        "emoji": "🔒",
        "title": "کپی کانال — کانال خصوصی و مدیریت",
        "commands": [
            f"`{PREFIX}کپی‌کانال پیدا` `اخبار` — جستجوی کانالِ خصوصی بینِ چت‌هات + آیدیِ کامل",
            f"`{PREFIX}کپی‌کانال ذخیره` `اخبار t.me/c/1234567890` — اسمِ دلخواه برای یک کانال",
            f"`{PREFIX}کپی‌کانال اسم‌ها` — لیستِ اسم‌های ذخیره‌شده",
            f"`{PREFIX}کپی‌کانال شروع` `@مقصد` + **ریپلای** روی پستِ کانال — مبدأ همان کانال",
            f"`{PREFIX}کپی‌کانال پوشه‌ها` — شماره‌ی پوشه‌ها",
            f"`{PREFIX}کپی‌کانال وضعیت` — پیشرفت، تاریخِ شروع، حالتِ «از این به بعد»",
            f"`{PREFIX}کپی‌کانال ادامه` `<شماره>` — ادامه؛ روی کارِ تمام‌شده = فقط پست‌های تازه",
            f"`{PREFIX}کپی‌کانال توقف` / `{PREFIX}کپی‌کانال ادامه` — مدیریتِ کپی",
            f"`{PREFIX}کپی‌کانال لیست` — کارهای اخیر",
            f"`{PREFIX}کپی‌کانال حذف` `<شماره>` — حذفِ کار",
            "📊 ~9000 پیام/ساعت • آلبوم‌ها سالم • ذخیره‌ی پیشرفت در دیتابیس",
            "⚠️ مقصد باید ادمین باشی • «محتوای محافظت‌شده» کپی نمی‌شه",
        ],
    },
    {
        "key": "daily_digest",
        "emoji": "🌙",
        "title": "خلاصه‌ی روزانه",
        "commands": [
            f"`{PREFIX}خلاصه‌روز` — نمایشِ وضعیت",
            f"`{PREFIX}خلاصه‌روز روشن/خاموش` — فعال/غیرفعال‌کردنِ ارسالِ خودکارِ شبانه",
            f"`{PREFIX}خلاصه‌روز حالت کلی/سفارشی` — خلاصه‌ی همه‌ی چت‌ها یا فقط چت‌های انتخابی",
            f"`{PREFIX}خلاصه‌روز زمان` `<HH:MM>` — ساعتِ ارسال (وقتِ محلی)",
            f"`{PREFIX}خلاصه‌روز افزودن/حذف` `<آیدیِ چت اختیاری>` — مدیریتِ لیستِ سفارشی",
            f"`{PREFIX}خلاصه‌روز لیست` / `{PREFIX}خلاصه‌روز پاک` — نمایش/پاک‌کردنِ لیستِ سفارشی",
            f"`{PREFIX}خلاصه‌روز الان` — اجرای فوری برای تست",
        ],
    },
    {
        "key": "media",
        "emoji": "🖼",
        "title": "رسانه و فایل",
        "commands": [
            f"`{PREFIX}بینایی` `<سوال>` — تحلیلِ عکس با AI (ریپلای)",
            f"`{PREFIX}تحلیل خطا/کد/جدول/نمودار` — 🖼 حالت‌های آماده (خطا→راه‌حل، استخراجِ کد...)",
            f"`{PREFIX}واترمارک` `<متن>` — واترمارکِ متنی روی عکسِ ریپلای‌شده",
            f"`{PREFIX}فشرده‌سازی` — کوچیک‌کردنِ عکس/ویدیوِ ریپلای‌شده",
            f"`{PREFIX}تبدیل` `<فرمت>` — تبدیل فرمتِ فایلِ ریپلای‌شده (webp→png، ogg→mp3، ...)",
            f"`{PREFIX}استیکر` `<نامِ‌پک> <ایموجی اختیاری>` — ساختِ استیکر از عکسِ ریپلای‌شده",
            f"`{PREFIX}استخراج‌متن` — استخراج متن از عکسِ ریپلای‌شده (پیش‌فرض: محلی/رایگان، فارسی+انگلیسی)",
            f"`{PREFIX}استخراج‌متن` `<en/fa>` — فقط یه زبانِ خاص (محلی)",
            f"`{PREFIX}استخراج‌متن ai` — با هوشِ مصنوعیِ Vision (بهتر برای دست‌نویس/کیفیتِ پایین، نیازمندِ AI_API_KEY)",
            f"`{PREFIX}عکس‌ترجمه` — ریپلای روی عکس؛ استخراجِ متن + ترجمه‌ی خودکار به فارسی (نیازمندِ AI_API_KEY)",
        ],
    },
    {
        "key": "ai",
        "emoji": "🤖",
        "title": "هوش مصنوعی",
        "commands": [
            f"`{PREFIX}پرسش` `<سوال>` — سوال از مدل زبانی (یا با ریپلای روی متن/صوت: خلاصه/تحلیلِ همون پیام)",
            f"`{PREFIX}پرسش آخرین باری که درباره … چی گفتیم؟` — 🔎 جستجوی معنایی در گفتگوهای قبلی (با نام/تاریخ/منبع/لینک)",
            f"`{PREFIX}ایندکس` — روشن/خاموش و پُرکردنِ ایندکسِ پیام‌ها برای جستجوی معنایی",
            f"`{PREFIX}عامل روشن/خاموش` — 🧠 Agent Mode: Context + Tool Calling + Router",
            f"`{PREFIX}خلاصه` `<عدد>` — خلاصه‌ی N پیامِ آخرِ همین چت (پیش‌فرض ۵۰)",
            f"`{PREFIX}ترجمه‌هوشمند` `<زبان> <متن>` — ترجمه با مدلِ زبانی (کیفیتِ بهتر، جدا از `{PREFIX}ترجمه`ی معمولی)",
            f"`{PREFIX}منشی هوش‌مصنوعی روشن/خاموش` — اتصالِ پاسخِ خودکارِ منشی به هوش مصنوعی",
            "⚠️ نیازمندِ متغیر محیطیِ `AI_API_KEY`؛ بدون اون فقط پیامِ راهنما می‌دن",
        ],
    },
    {
        "key": "command_router",
        "emoji": "🧠",
        "title": "روترِ دستوریِ هوشمند",
        "commands": [
            f"`{PREFIX}هوش` `<جمله‌ی آزاد>` — تشخیصِ خودکارِ دستور (یادآوری، یادداشت، ابزار، پروفایل، فونت، سرگرمی، ...)",
            f"`{PREFIX}هوش تایید` / `{PREFIX}هوش لغو` — تاییدِ صریح قبل از هر اجرایی",
            "⚠️ نیازمندِ همون `AI_API_KEY`",
        ],
    },
    {
        "key": "audio",
        "emoji": "🔊",
        "title": "صوت و متن",
        "commands": [
            f"`{PREFIX}رونویسی` — پیامِ صوتیِ ریپلای‌شده رو به متن تبدیل می‌کنه",
            f"`{PREFIX}رونویسی` `<سوال>` — رونویسی + پرسیدن از AI درباره‌ی همون متن",
            f"`{PREFIX}رونویسی کار` — 🎙 ویس → یادآوری/کارِ خودکار (اگر زمان داشته باشد)",
            f"`{PREFIX}متن‌به‌صوت` `<متن>` — متن رو به پیامِ صوتی تبدیل می‌کنه",
            "⚠️ از همون `AI_API_KEY` یِ بخشِ هوش مصنوعی استفاده می‌کنه",
        ],
    },
    {
        "key": "stats",
        "emoji": "📊",
        "title": "آمار",
        "commands": [
            f"`{PREFIX}آمار` — آمار کلی (دستورات، پیام‌ها، uptime، ...)",
            f"`{PREFIX}آمار چت‌ها` — آمار به‌تفکیک هر چت",
            f"`{PREFIX}آمار هوشمند` — 📈 تحلیلِ الگو + AI Insight",
            f"`{PREFIX}آمار بازنشانی` — پاک‌کردن همه‌ی آمار",
            f"`{PREFIX}آمارگراف` `<تعداد روز اختیاری>` — گراف تصویریِ فعالیتِ گروه (نیازمندِ matplotlib)",
        ],
    },
    {
        "key": "personal",
        "emoji": "🤖",
        "title": "دستیارِ شخصی",
        "commands": [
            f"`{PREFIX}داشبورد` — نمایِ یکجای همه‌چیز",
            f"`{PREFIX}کار` — 🔥 کارهای من (افزودن/انجام/امروز/عقب)",
            f"`{PREFIX}یادآوری` `<متنِ طبیعی>` — «فردا ساعت ۸ جلسه برو»",
            f"`{PREFIX}اتوپایل روشن/خاموش` — تحلیلِ خودکارِ پیام‌های خصوصی",
            f"`{PREFIX}اینباکس پاسخ` / `{PREFIX}اینباکس خلاصه`",
            f"`{PREFIX}XP` — 🎮 لِول و دستاوردها",
            f"`{PREFIX}سبک رسمی/دوستانه/کوتاه/طنز/حرفه‌ای` — سبکِ پیش‌فرضِ `.جواب`",
            f"`{PREFIX}تحلیل خطا/کد/جدول` — روی عکسِ ریپلای‌شده",
        ],
    },
    {
        "key": "security",
        "emoji": "🛡",
        "title": "امنیت و پشتیبان",
        "commands": [
            f"`{PREFIX}امنیت` — 🛡 SECURITY CENTER",
            f"`{PREFIX}سلامت` — وضعیت workerها و سرویس‌ها",
            f"`{PREFIX}نشست‌ها` — نشست‌های فعال (خروجِ اجباری: `خروج <hash>`)",
            f"`{PREFIX}پشتیبان تنظیمات` — بکاپ کامل (حافظه/کارها/زمان‌بندی)",
            f"`{PREFIX}بازیابی` — با ریپلای روی فایلِ بکاپ",
        ],
    },
]

# ============================ پنلِ V2 — Command Center مینیمال ====
# ساختار: HOME (Quick Actions + ۷ دسته + جستجو) → دسته → بخش → دستورها
# + ⭐ Favorites و 🕘 Recent (پایدار در settings، JSON) + 🔍 جستجوی دستور
#
# دسته‌های V2 (۹ گروهِ منطقی — «دکمه‌ی کم‌اهمیت در Home دیده نمی‌شود»):
V2_GROUPS = [
    {"key": "v_ai",         "emoji": "🧠", "title": "هوش مصنوعی",    "cats": ["ai", "ai_memory", "smart_reply", "command_router", "assistant"]},
    {"key": "v_productive", "emoji": "📥", "title": "بهره‌وری",       "cats": ["inbox", "personal", "scheduler", "channel_copy", "channel_copy_private", "notes", "profile"]},
    {"key": "v_tools",      "emoji": "🛠", "title": "ابزارها",        "cats": ["tools", "media", "audio", "global_search", "font", "general"]},
    {"key": "v_auto",       "emoji": "⚡", "title": "اتوماسیون",      "cats": ["automation", "notifications", "autopost", "daily_digest", "message_tracker"]},
    {"key": "v_group",      "emoji": "👮", "title": "مدیریتِ گروه",   "cats": ["admin", "msg", "poll"]},
    {"key": "v_fun",        "emoji": "🎮", "title": "سرگرمی",         "cats": ["fun"]},
    {"key": "v_plugins",    "emoji": "🧩", "title": "پلاگین‌ها",      "cats": ["plugins_cmd"]},
    {"key": "v_system",     "emoji": "⚙️", "title": "تنظیمات و سیستم", "cats": ["settings_center", "backup", "security", "health", "stats"]},
]

# Quick Actions: عملیاتِ پرکاربرد — یک هندلرِ واقعی از پروژه (نه فقط بخشِ پنل).
QUICK_ACTIONS = [
    {"emoji": "🧠", "label": "پرسش AI", "text": ".پرسش"},
    {"emoji": "📥", "label": "اینباکس", "text": ".اینباکس"},
    {"emoji": "📝", "label": "کارها", "text": ".کار"},
    {"emoji": "🎮", "label": "اتاقِ فرار", "text": ".فرار"},
]

# بخش‌هایی که دکمه‌ی ⭐/🕘 دارند (همه).
_FAV_KEY = "panel_favorites"
_RECENT_KEY = "panel_recent"

_CATEGORY_BY_KEY = {cat["key"]: cat for cat in CATEGORIES}
_V2_BY_KEY = {g["key"]: g for g in V2_GROUPS}

# اعتبارسنجی: هر cat باید دقیقاً در یک گروه باشد (در import-time چک می‌شود تا
# اضافه‌شدنِ دسته‌ی جدیدِ فراموش‌شده همان‌جا معلوم شود).
_assigned = [k for g in V2_GROUPS for k in g["cats"]]
assert len(_assigned) == len(set(_assigned)), "دسته‌ی تکراری در V2_GROUPS!"
_missing = set(_CATEGORY_BY_KEY) - set(_assigned)
assert not _missing, f"دسته‌های بی‌گروه: {_missing}"


# ------------------------------------------------------------- favorites/recent
async def _get_json_setting(key: str, default):
    from ..repositories import settings_repo

    return await settings_repo.get_setting_json(key, default)


async def _push_json_setting(key: str, value: str, max_items: int):
    """value را به ابتدای لیستِ JSON-key اضافه می‌کند (بدونِ تکرار، سقف‌دار).

    برای _RECENT_KEY ورودی به‌صورتِ [cat_key, unix_ts] ذخیره می‌شود تا داشبورد
    بتواند «چند دقیقه پیش» را نشان دهد؛ رکوردهای قدیمیِ رشته‌ای هم خوانده می‌شوند.
    """
    import time as _time

    from ..repositories import settings_repo

    items = await settings_repo.get_setting_json(key, [])
    if not isinstance(items, list):
        items = []
    # نرمال‌سازی: هر آیتم = [key_str, ts_float]
    norm = []
    for it in items:
        if isinstance(it, list) and it and isinstance(it[0], str):
            norm.append([it[0], float(it[1]) if len(it) > 1 else 0.0])
        elif isinstance(it, str):
            norm.append([it, 0.0])
    norm = [it for it in norm if it[0] != value]
    norm.insert(0, [value, _time.time()])
    await settings_repo.set_setting_json(key, norm[:max_items])


async def _toggle_favorite(cat_key: str) -> bool:
    from ..repositories import settings_repo

    favs = await settings_repo.get_setting_json(_FAV_KEY, [])
    if not isinstance(favs, list):
        favs = []
    if cat_key in favs:
        favs.remove(cat_key)
        state = False
    else:
        favs.insert(0, cat_key)
        state = True
    await settings_repo.set_setting_json(_FAV_KEY, favs[:10])
    return state


def _cat_label(cat_key: str) -> str:
    cat = _CATEGORY_BY_KEY.get(cat_key)
    return f"{cat['emoji']} {cat['title']}" if cat else cat_key


# ------------------------------------------------------------- home
def build_home_text():
    total_commands = sum(len(c["commands"]) for c in CATEGORIES)
    return (
        "🤖 **HADI ASSISTANT**\n"
        f"{_divider()}\n"
        f"🟢 آنلاین   •   ⚙️ {total_commands} دستور   •   🔡 `{PREFIX}`\n"
        "از دکمه‌های زیر انتخاب کن ⬇️"
    )


def build_home_buttons(favorites=None, recents=None):
    favorites = favorites or []
    rows = []

    # ⭐ موردعلاقه‌ها (اگر هست) — دو‌ستونه
    fav_rows = []
    row = []
    for key in favorites[:6]:
        if key in _CATEGORY_BY_KEY:
            cat = _CATEGORY_BY_KEY[key]
            row.append(Button.inline(f"⭐ {cat['emoji']} {cat['title']}", _cb(f"cat:{key}")))
            if len(row) == 2:
                fav_rows.append(row)
                row = []
    if row:
        fav_rows.append(row)
    if fav_rows:
        rows.append([Button.inline("⭐ موردعلاقه‌ها", _cb("noop"))])
        rows.extend(fav_rows)

    # دسته‌های اصلی — دو‌ستونه (۸ دکمه = ۴ ردیف)
    row = []
    for g in V2_GROUPS:
        row.append(Button.inline(f"{g['emoji']} {g['title']}", _cb(f"grp:{g['key']}")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # 🔍 جستجو + 🕘 اخیر + داشبورد/بستن
    rows.append([Button.inline("🔍 جستجوی دستور", _cb("search"))])
    if recents:
        rows.append([Button.inline("🕘 اخیراً استفاده‌شده", _cb("recent"))])
    rows.append([
        Button.inline("📊 داشبورد", _cb("dash")),
        Button.inline("✖️ بستن پنل", _cb("close")),
    ])
    return rows


def build_search_results_text(query: str, matches):
    lines = [f"🔎 **نتایجِ «{query}»** ({len(matches)})", _divider(), ""]
    for cat_key, cmd_line in matches[:10]:
        cat = _CATEGORY_BY_KEY[cat_key]
        lines.append(f"{cat['emoji']} {cmd_line}")
    if len(matches) > 10:
        lines.append(f"\n… و {len(matches) - 10} موردِ دیگر")
    return "\n".join(lines)


def build_search_buttons(matches):
    rows = []
    row = []
    for cat_key, _ in matches[:10]:
        cat = _CATEGORY_BY_KEY[cat_key]
        row.append(Button.inline(f"{cat['emoji']} {cat['title']}", _cb(f"cat:{cat_key}")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Button.inline("🔙 بازگشت", _cb("home"))])
    return rows


def _recent_keys(recents):
    """فرمتِ قدیم (str) و جدید ([key, ts]) را به [(key, ts)] نرمال می‌کند."""
    out = []
    for it in recents[:8]:
        if isinstance(it, list) and it and isinstance(it[0], str):
            out.append((it[0], float(it[1]) if len(it) > 1 else 0.0))
        elif isinstance(it, str):
            out.append((it, 0.0))
    return [it for it in out if it[0] in _CATEGORY_BY_KEY]


def build_recent_text(recents):
    import time as _time

    lines = ["🕘 **اخیراً استفاده‌شده**", _divider(), ""]
    for key, ts in _recent_keys(recents):
        cat = _CATEGORY_BY_KEY[key]
        ago = ""
        if ts > 0:
            mins = int((_time.time() - ts) // 60)
            ago = f" ({mins}د پیش)" if mins < 60 else f" ({mins // 60}س پیش)"
        lines.append(f"{cat['emoji']} **{cat['title']}**{ago} — {len(cat['commands'])} دستور")
    return "\n".join(lines)


def build_recent_buttons(recents):
    rows = []
    row = []
    for key, _ts in _recent_keys(recents):
        cat = _CATEGORY_BY_KEY[key]
        row.append(Button.inline(f"{cat['emoji']} {cat['title']}", _cb(f"cat:{key}")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Button.inline("🔙 بازگشت", _cb("home"))])
    return rows


def build_group_text(group):
    lines = [f"{group['emoji']} **{group['title']}**", _divider(), ""]
    for key in group["cats"]:
        cat = _CATEGORY_BY_KEY[key]
        lines.append(f"{cat['emoji']} **{cat['title']}** — {len(cat['commands'])} دستور")
    lines += ["", _divider(), "یکی از بخش‌ها رو از دکمه‌های پایین باز کن."]
    return "\n".join(lines)


def build_group_buttons(group):
    rows = []
    row = []
    for key in group["cats"]:
        cat = _CATEGORY_BY_KEY[key]
        row.append(Button.inline(f"{cat['emoji']} {cat['title']}", _cb(f"cat:{key}")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Button.inline("🔙 بازگشت", _cb("home")), Button.inline("✖️ بستن", _cb("close"))])
    return rows



def build_category_text(cat):
    # دستورها (شامل {PREFIX}) با ›، نکته‌ها/توضیح‌های آزاد با 〰 متمایز می‌شوند.
    lines = []
    for line in cat["commands"]:
        if f"`{PREFIX}" in line or line.startswith("`"):
            lines.append(f"› {line}")
        else:
            lines.append(f"ℹ️ {line}")
    body = "\n".join(lines)
    return (
        f"{cat['emoji']} **{cat['title']}**  ({len(cat['commands'])} مورد)\n"
        f"{_divider()}\n\n"
        f"{body}\n\n"
        f"{_divider()}\n"
        "➜ برای اجرا، دستور رو با اکانت خودت (نه این ربات) توی چت مقصد بفرست."
    )


def build_category_buttons():
    return [[
        Button.inline("🔙 بازگشت", _cb("home")),
        Button.inline("✖️ بستن", _cb("close")),
    ]]


# ---------------------------------------------------------------------------
# نکته‌ی مهم: تلگرام دکمه‌های شیشه‌ای (inline keyboard) رو فقط برای پیام‌های
# ارسالی از طرف یه بات واقعی (BotFather) نمایش می‌ده، نه پیام‌های اکانت
# شخصی/سلف‌بات. برای همین یه بات کمکی (runtime.bot_client، با BOT_TOKEN) لازمه.
#
# برای اینکه پنل توی همون چتی که «.پنل» زده می‌شه نمایش داده بشه (نه فقط توی
# چت خصوصیِ خود بات کمکی)، از حالت inline بات کمکی استفاده می‌کنیم:
#   ۱) اکانتِ خودِ سلف‌بات (client) با client.inline_query(...) یه نتیجه‌ی
#      inline از بات کمکی می‌گیره و با result.click(event.chat_id) همون
#      نتیجه (که دکمه‌های واقعی داره، چون منشأش باته) رو توی همین چت می‌فرسته؛
#      پیام با برچسبِ «via @نام‌بات» ولی با دکمه‌های کاملاً کاربردی نمایش داده
#      می‌شه، و بعد پیامِ دستورِ «.پنل» پاک می‌شه.
#   ۲) این کار فقط وقتی جواب می‌ده که حالت inline روی بات کمکی فعال باشه
#      (توی @BotFather → بات موردنظر → Bot Settings → Inline Mode → روشن).
#      اگه فعال نباشه (یا هر خطای دیگه‌ای پیش بیاد)، به‌جاش یه لینکِ باز کردنِ
#      چتِ خصوصیِ بات کمکی فرستاده می‌شه (روش قدیمی، به‌عنوان fallback).
#   ۳) کلیک‌های داخلِ پنل (دکمه‌ها) چه توی چتِ خصوصیِ بات باشن چه inline توی
#      یه چتِ دیگه، همگی از طریق همون CallbackQuery پایین مدیریت می‌شن -
#      تلتون خودش تشخیص می‌ده پیام عادیه یا inline و edit رو درست انجام می‌ده.
# ---------------------------------------------------------------------------


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پنل", "panel"], arg=False)))
async def panel_open_handler(event):
    if runtime.bot_client is None or not runtime.BOT_USERNAME:
        await event.edit(
            "⚠️ **پنل دکمه‌ای غیرفعاله**\n"
            f"{_divider()}\n"
            "برای فعال‌سازی:\n"
            "۱. توی @BotFather یه بات جدید بساز.\n"
            "۲. توکنش رو توی متغیر محیطی `BOT_TOKEN` بذار.\n"
            "۳. سلف‌بات رو ری‌استارت کن."
        )
        return

    try:
        results = await client.inline_query(runtime.BOT_USERNAME, "panel")
        if not results:
            raise RuntimeError("no inline results")
        await results[0].click(
            event.chat_id,
            reply_to=event.reply_to_msg_id,
            silent=False,
        )
        await event.delete()
    except Exception:
        # حالت inline روی بات کمکی فعال نیست (یا خطای دیگه‌ای پیش اومده) -
        # fallback به لینکِ باز کردنِ چتِ خصوصیِ بات کمکی.
        link = f"https://t.me/{runtime.BOT_USERNAME}?start=panel"
        text = (
            "👑 **پنل مدیریت سلف‌بات** 👑\n"
            f"{_divider()}\n\n"
            "برای نمایش پنل همین‌جا، اول باید حالت Inline Mode بات کمکی رو توی\n"
            "@BotFather → botموردنظر → Bot Settings → Inline Mode روشن کنی.\n\n"
            f"فعلاً می‌تونی از طریق چتِ خصوصیِ بات باز کنیش: {link}"
        )
        await event.edit(text, link_preview=False)


if runtime.bot_client is not None:

    @runtime.bot_client.on(events.NewMessage(incoming=True, pattern=r"^/(start|panel)\b"))
    async def panel_bot_start_handler(event):
        if runtime.SELF_ID is not None and event.sender_id != runtime.SELF_ID:
            await event.respond("⛔️ این ربات فقط برای صاحب اکانت است.")
            return
        await event.respond(build_home_text(), buttons=build_home_buttons())

    @runtime.bot_client.on(events.InlineQuery)
    async def panel_bot_inline_handler(event):
        # فقط صاحب اکانت (خود سلف‌بات) اجازه‌ی گرفتنِ نتیجه‌ی inline رو داره.
        if runtime.SELF_ID is not None and event.sender_id != runtime.SELF_ID:
            await event.answer([])
            return

        builder = event.builder
        result = builder.article(
            title="👑 باز کردن پنل مدیریت",
            description=f"{len(V2_GROUPS)} دسته / {len(CATEGORIES)} بخش / {sum(len(c['commands']) for c in CATEGORIES)} دستور — با جستجو و موردعلاقه‌ها",
            text=build_home_text(),
            buttons=build_home_buttons(),
        )
        await event.answer([result])

    @runtime.bot_client.on(events.CallbackQuery(pattern=rb"^p:"))
    async def panel_bot_callback_handler(event):
        # فقط صاحب اکانت (خود سلف‌بات) اجازه‌ی تعامل با پنل رو داره
        if runtime.SELF_ID is not None and event.sender_id != runtime.SELF_ID:
            await event.answer("⛔️ این پنل فقط برای مالک اکانت است.", alert=True)
            return

        data = event.data.decode()
        action = data[len(CB_PREFIX):]

        if action == "home":
            favs = await _get_json_setting(_FAV_KEY, [])
            recents = await _get_json_setting(_RECENT_KEY, [])
            await event.edit(build_home_text(), buttons=build_home_buttons(favs, recents))
            await event.answer()
            return

        if action == "noop":
            await event.answer()
            return

        if action == "recent":
            recents = await _get_json_setting(_RECENT_KEY, [])
            await event.edit(build_recent_text(recents), buttons=build_recent_buttons(recents))
            await event.answer()
            return

        if action == "search":
            await event.answer("🔍 توی چتِ خودت بنویس: `.پنل پیدا <عبارت>`", alert=True)
            return

        if action.startswith("star:"):
            key = action[len("star:"):]
            is_fav = await _toggle_favorite(key)
            favs = await _get_json_setting(_FAV_KEY, [])
            cat = _CATEGORY_BY_KEY.get(key)
            if cat:
                label = "⭐ حذف از موردعلاقه‌ها" if is_fav else "⭐ افزودن به موردعلاقه‌ها"
                await event.edit(
                    build_category_text(cat),
                    buttons=[[Button.inline(label, _cb(f"star:{key}")),
                              Button.inline("🔙 بازگشت", _cb("home")),
                              Button.inline("✖️ بستن", _cb("close"))]],
                )
            await event.answer("⭐ اضافه شد" if is_fav else "از موردعلاقه‌ها حذف شد")
            return

        if action == "dash":
            # 📊 داشبورد داخلِ خودِ پنل — مثل بقیه‌ی صفحات
            try:
                from .dashboard import build_dashboard, _dashboard_buttons

                text = await build_dashboard()
                await event.edit(text, buttons=_dashboard_buttons())
            except Exception as e:
                await event.answer(f"❌ خطا در داشبورد: {e}", alert=True)
                return
            await event.answer()
            return

        if action == "dashcfg":
            # ⚙️ تنظیماتِ داشبورد: روشن/خاموشِ هر بخش
            try:
                from .dashboard import _dash_sections_on

                on = await _dash_sections_on()
                rows = [[Button.inline(
                    f"{'✅' if is_on else '⬜'} {label}", _cb(f"dashcfg:{k}")
                )] for k, label in on.items()]
                rows.append([Button.inline("🔙 بازگشت", _cb("home"))])
                await event.edit(
                    "⚙️ **تنظیماتِ داشبورد**\nهر بخش را روشن/خاموش کن:",
                    buttons=rows,
                )
            except Exception as e:
                await event.answer(f"❌ {e}", alert=True)
                return
            await event.answer()
            return

        if action.startswith("dashcfg:"):
            try:
                from .dashboard import _dash_sections_on, _toggle_dash_section

                new_state = await _toggle_dash_section(action[len("dashcfg:"):])
                if new_state is None:
                    await event.answer()
                    return
                on = await _dash_sections_on()
                rows = [[Button.inline(
                    f"{'✅' if is_on else '⬜'} {label}", _cb(f"dashcfg:{k}")
                )] for k, label in on.items()]
                rows.append([Button.inline("🔙 بازگشت", _cb("home"))])
                await event.edit("⚙️ **تنظیماتِ داشبورد**\nهر بخش را روشن/خاموش کن:", buttons=rows)
                await event.answer("تغییر کرد ✓")
            except Exception as e:
                await event.answer(f"❌ {e}", alert=True)
            return

        if action.startswith("refresh:"):
            if action[len("refresh:"):] == "dashboard":
                try:
                    from .dashboard import build_dashboard, _dashboard_buttons

                    text = await build_dashboard()
                    await event.edit(text, buttons=_dashboard_buttons())
                    await event.answer("🔄 بروز شد")
                except Exception as e:
                    await event.answer(f"❌ {e}", alert=True)
                return
            await event.answer()
            return

        if action == "close":
            # نکته‌ی مهم: `event.delete()` فقط وقتی کار می‌کنه که پیامِ پنل یه
            # پیامِ عادیِ خودِ بات کمکی باشه (یعنی توی چتِ خصوصیِ خودِ بات).
            # وقتی پنل با ترفندِ inline (client.inline_query(...).click(...))
            # توی یه چت/گروهِ دیگه فرستاده می‌شه، تلگرام فقط یه inline_message_id
            # به بات می‌ده - و API ای برای حذفِ پیام از طریقِ همون شناسه وجود
            # نداره (فقط edit ازش پشتیبانی می‌شه)، برای همین `event.delete()`
            # اونجا سرِ همچین پیام‌هایی fail می‌شه و دکمه‌ی «بستن» بی‌اثر
            # به‌نظر می‌رسید. راه‌حل: اول با edit (که هم توی چتِ خصوصی هم
            # inline کار می‌کنه) دکمه‌ها رو برمی‌داریم و متن رو «بسته‌شد» می‌کنیم،
            # و فقط اگه واقعاً یه پیامِ عادی (نه inline) بود، تلاش می‌کنیم
            # کاملاً حذفش هم بکنیم (برای تمیزیِ بیشتر توی چتِ خودِ بات).
            try:
                await event.edit("✖️ پنل بسته شد.", buttons=None)
            except Exception:
                pass
            try:
                if getattr(event.query, "msg_id", None):
                    await event.delete()
            except Exception:
                pass
            await event.answer()
            return

        if action.startswith("grp:"):
            gkey = action[len("grp:"):]
            group = _V2_BY_KEY.get(gkey)
            if group is None:
                await event.answer("یافت نشد.", alert=True)
                return
            await event.edit(build_group_text(group), buttons=build_group_buttons(group))
            await event.answer()
            return

        if action.startswith("cat:"):
            key = action[len("cat:"):]
            cat = _CATEGORY_BY_KEY.get(key)
            if cat is None:
                await event.answer("یافت نشد.", alert=True)
                return
            # 🕘 ثبت در «اخیراً استفاده‌شده» (پایدار)
            await _push_json_setting(_RECENT_KEY, key, max_items=8)
            favs = await _get_json_setting(_FAV_KEY, [])
            star_label = "💔 حذف از موردعلاقه‌ها" if key in favs else "⭐ افزودن به موردعلاقه‌ها"
            # دکمه‌ی بازگشت در سطحِ بخش باید به گروهِ والدش برگردد
            parent = next((g for g in V2_GROUPS if key in g["cats"]), None)
            back_cb = _cb(f"grp:{parent['key']}") if parent else _cb("home")
            await event.edit(
                build_category_text(cat),
                buttons=[
                    [Button.inline(star_label, _cb(f"star:{key}"))],
                    [Button.inline("🔙 بازگشت", back_cb), Button.inline("✖️ بستن", _cb("close"))],
                ],
            )
            await event.answer()
            return

        await event.answer()

def _search_commands(query: str):
    """جستجوی دستورها بر اساسِ نامِ دستور/کلیدواژه در متنِ خط؛ خروجی: [(cat_key, line)]"""
    q = query.strip().lower()
    if not q:
        return []
    results = []
    for cat in CATEGORIES:
        for line in cat["commands"]:
            hay = line.lower()
            # هم نامِ دستور (بعد از نقطه) هم کلِ خط
            if q in hay:
                results.append((cat["key"], line))
    return results


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پنل پیدا", "panel find"])))
async def panel_search_handler(event):
    """`.پنل پیدا <عبارت>` — جستجو در ۲۰۰+ دستورِ پنل."""
    query = (event.pattern_match.group(1) or "").strip()
    if not query:
        return await event.edit(f"مثال: `{PREFIX}پنل پیدا یادآوری`")
    matches = _search_commands(query)
    if not matches:
        return await event.edit(f"🔎 چیزی برای «{query}» پیدا نشد.")
    await event.edit(
        build_search_results_text(query, matches),
        buttons=build_search_buttons(matches),
    )
