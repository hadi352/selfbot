#!/usr/bin/env python3
"""
اسکریپت بررسی پیش از استارت - برای جلوگیری از کرش‌لوپ روی Railway
این اسکریپت قبل از main.py اجرا می‌شه و متغیرهای ضروری رو چک می‌کنه
"""
import os
import sys

def check_required_vars():
    """بررسی متغیرهای ضروری محیطی"""
    errors = []
    warnings = []
    
    # ضروری: Telegram API
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    session_string = os.getenv("SESSION_STRING", "")
    
    if not api_id or not api_hash:
        errors.append(
            "❌ API_ID و API_HASH تنظیم نشده‌اند\n"
            "   → از my.telegram.org → API development tools بگیرید\n"
            "   → در Railway Variables یا .env تنظیم کنید"
        )
    else:
        try:
            int(api_id)
        except ValueError:
            errors.append(f"❌ API_ID باید عدد باشد، نه: {api_id}")
    
    if not session_string:
        warnings.append(
            "⚠️  SESSION_STRING خالی است\n"
            "   → برای Railway باید StringSession بسازید:\n"
            "   → python generate_session.py\n"
            "   → خروجی را در متغیر SESSION_STRING بگذارید"
        )
    elif len(session_string) < 50:
        errors.append(
            "❌ SESSION_STRING ناقص است (خیلی کوتاه)\n"
            "   → مطمئن شوید تمام خروجی generate_session.py را کپی کردید"
        )
    
    # ضروری: Database
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        errors.append(
            "❌ DATABASE_URL تنظیم نشده\n"
            "   → در Railway: + New → Database → PostgreSQL\n"
            "   → متغیر DATABASE_URL خودکار اضافه می‌شود"
        )
    elif not database_url.startswith(("postgres://", "postgresql://")):
        warnings.append(
            f"⚠️  DATABASE_URL فرمت عجیبی دارد: {database_url[:30]}..."
        )
    
    # اختیاری: AI
    ai_api_key = os.getenv("AI_API_KEY", "")
    if not ai_api_key:
        warnings.append(
            "⚠️  AI_API_KEY تنظیم نشده - قابلیت‌های هوش مصنوعی غیرفعال هستند\n"
            "   → برای استفاده از .پرسش، .خلاصه، منشی AI، این کلید را اضافه کنید"
        )
    
    # نمایش نتایج
    if errors:
        print("\n" + "="*70)
        print("🚨 خطاهای حیاتی - ربات نمی‌تواند راه‌اندازی شود:")
        print("="*70)
        for error in errors:
            print(f"\n{error}")
        print("\n" + "="*70)
        print("\n📖 راهنمای کامل: مطالعه کنید RAILWAY_SETUP.md\n")
        return False
    
    if warnings:
        print("\n" + "="*70)
        print("⚠️  هشدارها (ربات کار می‌کند ولی برخی قابلیت‌ها محدود هستند):")
        print("="*70)
        for warning in warnings:
            print(f"\n{warning}")
        print("\n" + "="*70 + "\n")
    
    print("✅ تمام متغیرهای ضروری تنظیم شده‌اند - شروع راه‌اندازی...\n")
    return True


if __name__ == "__main__":
    if not check_required_vars():
        sys.exit(1)
    sys.exit(0)
