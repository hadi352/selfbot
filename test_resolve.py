"""
اسکریپت تست سریع کپی کانال
استفاده: python test_resolve.py @channel1 @channel2
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_resolve():
    if len(sys.argv) < 3:
        print("استفاده: python test_resolve.py @channel1 @channel2")
        return 1
    
    from bot.runtime import client
    from bot.handlers.channel_copy import _resolve, parse_chat_ref, _title
    
    src_raw = sys.argv[1]
    dst_raw = sys.argv[2]
    
    print(f"🔍 تست resolve برای:")
    print(f"  مبدأ: {src_raw}")
    print(f"  مقصد: {dst_raw}")
    print()
    
    # اتصال به تلگرام
    await client.connect()
    
    try:
        # تست مبدأ
        print(f"📌 Parse مبدأ...")
        src_ref = parse_chat_ref(src_raw)
        print(f"   ✅ {src_ref}")
        
        print(f"🔄 Resolve مبدأ...")
        src = await _resolve(src_ref, None)
        if src:
            print(f"   ✅ پیدا شد: {_title(src)} (ID: {src.id})")
        else:
            print(f"   ❌ پیدا نشد")
            return 1
        
        # تست مقصد
        print()
        print(f"📌 Parse مقصد...")
        dst_ref = parse_chat_ref(dst_raw)
        print(f"   ✅ {dst_ref}")
        
        print(f"🔄 Resolve مقصد...")
        dst = await _resolve(dst_ref, None)
        if dst:
            print(f"   ✅ پیدا شد: {_title(dst)} (ID: {dst.id})")
        else:
            print(f"   ❌ پیدا نشد")
            return 1
        
        print()
        print("✅ هر دو کانال با موفقیت resolve شدند!")
        return 0
        
    except Exception as e:
        print(f"❌ خطا: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(test_resolve()))
