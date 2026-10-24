# راهنمای دیپلوی روی Railway

## مراحل نصب

### ۱. ساخت پروژه در Railway

1. وارد [Railway](https://railway.app) شوید
2. یک پروژه جدید بسازید
3. از GitHub repository متصل کنید: `https://github.com/hadi3785/selfbot`

### ۲. افزودن PostgreSQL Database

1. در پروژه Railway روی **+ New** کلیک کنید
2. **Database** → **PostgreSQL** را انتخاب کنید
3. Railway به‌صورت خودکار متغیر `DATABASE_URL` را تنظیم می‌کند

### ۳. تنظیم متغیرهای محیطی (Environment Variables)

در تب **Variables** سرویس اصلی، این متغیرها را اضافه کنید:

#### ✅ ضروری (بدون این‌ها کرش می‌کند):

```bash
# از my.telegram.org → API development tools
API_ID=1234567
API_HASH=0123456789abcdef0123456789abcdef

# ساخت SESSION_STRING:
# روی کامپیوتر خودتان: python generate_session.py
# خروجی را کپی کنید و اینجا بگذارید
SESSION_STRING=1BVtsOLwBu...طولانی...

# DATABASE_URL خودکار توسط Railway ست می‌شود
```

#### 🔧 اختیاری (برای قابلیت‌های اضافی):

```bash
# بات کمکی برای پنل دکمه‌ای (اختیاری)
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# پیشوند دستورات (پیش‌فرض: .)
PREFIX=.

# هوش مصنوعی (برای .پرسش، .خلاصه، منشی)
AI_API_KEY=sk-...
AI_API_BASE=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# اختلاف زمانی با UTC (تهران = 3.5)
TIMEZONE_OFFSET=3.5
```

### ۴. دیپلوی

1. Railway به‌صورت خودکار build و deploy می‌کند
2. در تب **Logs** وضعیت را بررسی کنید
3. اگر پیام زیر را دیدید، سلف‌بات آماده است:

```
سلف‌بات با اکانت [نام شما] روشن شد
```

## 🚨 عیب‌یابی مشکلات رایج

### کرش با پیام "Missing environment variable"

**علت**: `API_ID`، `API_HASH` یا `SESSION_STRING` تنظیم نشده

**راه حل**:
1. مطمئن شوید هر سه متغیر در Railway Variables تنظیم شده‌اند
2. `API_ID` باید **عدد** باشد (بدون گیومه)
3. `SESSION_STRING` باید کامل کپی شود (رشته بسیار طولانی)

### کرش با "DATABASE_URL تنظیم نشده"

**علت**: PostgreSQL plugin اضافه نشده

**راه حل**:
1. **+ New** → **Database** → **PostgreSQL**
2. یک دقیقه صبر کنید تا متغیر `DATABASE_URL` خودکار اضافه شود
3. دوباره deploy کنید

### کرش با "AuthKeyDuplicatedError"

**علت**: همان `SESSION_STRING` هم‌زمان در دو جای مختلف استفاده می‌شود

**راه حل**:
1. SESSION قدیمی را ببندید (تمام دیپلوی‌های دیگر و اجرای محلی)
2. یک `SESSION_STRING` جدید بسازید:
   ```bash
   python generate_session.py
   ```
3. SESSION جدید را در Railway Variables بگذارید

### کرش در مرحله Migration

**علت**: مشکل در اتصال به PostgreSQL

**راه حل**:
1. مطمئن شوید PostgreSQL plugin در حالت **Active** است
2. در Variables بررسی کنید `DATABASE_URL` وجود دارد
3. **Restart** سرویس را امتحان کنید

### ربات آنلاین نمی‌شود

**بررسی**:
1. در تب **Logs** پیغام‌های خطا را ببینید
2. تست کنید SESSION معتبر است:
   ```bash
   # روی کامپیوتر خودتان با همان SESSION_STRING
   python -c "from telethon.sync import TelegramClient; client = TelegramClient('test', API_ID, API_HASH).start(); print('OK')"
   ```

## 📝 نکات مهم

1. **هرگز** `SESSION_STRING` را public نکنید (نه در GitHub، نه جایی)
2. **محدودیت‌های تلگرام**: استفاده افراطی از ربات ممکن است اکانت را محدود کند
3. **بکاپ**: با دستور `.پشتیبان` از تنظیمات بکاپ بگیرید
4. **لاگ‌ها**: Railway لاگ‌های ۷ روز اخیر را نگه می‌دارد

## 🔄 به‌روزرسانی

وقتی کد جدید push می‌شود، Railway خودکار rebuild و redeploy می‌کند.

برای آپدیت دستی:
1. **⚙️ Settings** → **Redeploy**
2. یا در GitHub یک commit جدید push کنید

## 📊 مانیتورینگ

دستورات مفید برای بررسی وضعیت:
- `.سلامت` - وضعیت سیستم و workers
- `.آمار` - آمار استفاده
- `.پینگ` - تست اتصال

## پشتیبانی

اگر مشکلی حل نشد:
1. لاگ‌های کامل Railway را بررسی کنید
2. Issue در GitHub بسازید
3. اطمینان حاصل کنید تمام متغیرهای ضروری ست شده‌اند
