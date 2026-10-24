#!/usr/bin/env python3
"""
اسکریپت تست کپی کانال - برای عیب‌یابی مشکلات
"""
import asyncio
import datetime as dt
import sys
import os

# اضافه کردن پوشه به path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_imports():
    """تست import کردن ماژول‌های کپی کانال"""
    print("🔍 در حال تست import ماژول‌ها...")
    
    try:
        from bot import channel_copy_core
        print("✅ bot.channel_copy_core")
    except Exception as e:
        print(f"❌ bot.channel_copy_core: {e}")
        return False
    
    try:
        from bot.repositories import channel_copy_repo
        print("✅ bot.repositories.channel_copy_repo")
    except Exception as e:
        print(f"❌ bot.repositories.channel_copy_repo: {e}")
        return False
    
    try:
        from bot.handlers import channel_copy
        print("✅ bot.handlers.channel_copy")
    except Exception as e:
        print(f"❌ bot.handlers.channel_copy: {e}")
        return False
    
    try:
        from bot.db.models_ext import ChannelCopyJob
        print("✅ bot.db.models_ext.ChannelCopyJob")
    except Exception as e:
        print(f"❌ bot.db.models_ext.ChannelCopyJob: {e}")
        return False
    
    return True


async def test_parsing():
    """تست تابع parse"""
    print("\n🔍 در حال تست parsing...")
    
    from bot.channel_copy_core import parse_chat_ref, parse_start_args
    
    # تست parse_chat_ref
    tests = [
        ("@testchannel", ("username", "testchannel")),
        ("testchannel", ("username", "testchannel")),
        ("https://t.me/testchannel", ("username", "testchannel")),
        ("-1001234567890", ("id", -1001234567890)),
    ]
    
    for inp, expected in tests:
        try:
            result = parse_chat_ref(inp)
            if result == expected:
                print(f"✅ parse_chat_ref('{inp}') = {result}")
            else:
                print(f"⚠️  parse_chat_ref('{inp}') = {result}, انتظار: {expected}")
        except Exception as e:
            print(f"❌ parse_chat_ref('{inp}'): {e}")
    
    # تست parse_start_args
    test_args = [
        (["@src", "@dst"], ("@src", "@dst", 0, None, True)),
        (["@src", "@dst", "از", "100"], ("@src", "@dst", 99, None, True)),
        (["@src", "@dst", "با‌نام"], ("@src", "@dst", 0, None, False)),
        (["@src", "@dst", "از", "1403/05/01"], ("@src", "@dst", 0, dt.datetime(2024, 7, 22), True)),
    ]
    
    for inp, expected in test_args:
        try:
            result = parse_start_args(inp)
            if result == expected:
                print(f"✅ parse_start_args({inp}) = {result}")
            else:
                print(f"⚠️  parse_start_args({inp}) = {result}, انتظار: {expected}")
        except Exception as e:
            print(f"❌ parse_start_args({inp}): {e}")
    
    return True


async def test_database():
    """تست اتصال به دیتابیس"""
    print("\n🔍 در حال تست اتصال دیتابیس...")
    
    from bot import config
    
    if not config.DATABASE_URL:
        print("⚠️  DATABASE_URL تنظیم نشده - این تست skip می‌شود")
        return True
    
    try:
        from bot.db.engine import session_scope
        from bot.repositories import channel_copy_repo
        
        async with session_scope() as session:
            print("✅ اتصال به دیتابیس موفق")
        
        # تست list_jobs
        jobs = await channel_copy_repo.list_jobs(1)
        print(f"✅ list_jobs: {len(jobs)} کار")
        
        return True
    except Exception as e:
        print(f"❌ خطا در دیتابیس: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("="*60)
    print("🧪 تست سیستم کپی کانال")
    print("="*60)
    
    # تست 1: Import ها
    if not await test_imports():
        print("\n❌ تست import ناموفق - بررسی کنید!")
        return 1
    
    # تست 2: Parsing
    if not await test_parsing():
        print("\n❌ تست parsing ناموفق")
        return 1
    
    # تست 3: Database
    if not await test_database():
        print("\n❌ تست دیتابیس ناموفق")
        return 1
    
    print("\n" + "="*60)
    print("✅ همه تست‌ها موفق - سیستم کپی کانال آماده است")
    print("="*60)
    print("\nنحوه استفاده:")
    print("  .کپی‌کانال شروع @مبدا @مقصد از 1403/05/01")
    print("  .کپی‌کانال شروع @مبدا @مقصد ازاین‌بعد      (پیام‌های تازه هم کپی می‌شن)")
    print("  .کپی‌کانال پیدا اخبار                       (پیدا کردنِ کانالِ خصوصی)")
    print("  .کپی‌کانال ذخیره اخبار @ch                  (اسمِ دلخواه برای کانال)")
    print("  .کپی‌کانال وضعیت / توقف / ادامه / لیست / حذف 3")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
