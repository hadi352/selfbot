"""۱۶) هوش مصنوعی: `.پرسش` (سوال/خلاصه‌سازیِ یه پیام)، `.خلاصه` (خلاصه‌ی N
پیامِ آخرِ چت)، و `.ترجمه‌هوشمند` (ترجمه با مدلِ زبانی به‌جای سرویسِ ترجمه‌ی ساده)

همه‌ی این‌ها از هسته‌ی مشترکِ bot/ai.py (ask_ai) استفاده می‌کنن که یه wrapper
روی APIِ چت‌تکمیلیِ سازگار با OpenAI ه. برای فعال‌سازی باید متغیرِ محیطیِ
`AI_API_KEY` رو ست کنی (اختیاری: `AI_MODEL`/`AI_API_BASE` برای سرویس‌های
دیگه) - وگرنه این دستورات فقط یه پیامِ راهنما می‌دن و بقیه‌ی سلف‌بات عادی
کار می‌کنه.

نکته: `.منشی هوش‌مصنوعی روشن/خاموش` (توی bot/handlers/assistant.py تعریف
شده) باعث می‌شه پاسخِ خودکارِ منشی هم به‌جای متنِ ثابت، از همین هسته تولید
بشه - یعنی این قابلیت هم می‌تونه جدا (`.پرسش`/`.خلاصه`) استفاده بشه، هم به
منشی وصل بشه.

`.ترجمه‌هوشمند` جدا از `.ترجمه`ی معمولی (توی bot/handlers/tools.py، بدونِ
نیاز به AI_API_KEY) عمل می‌کنه: کندتره ولی چون از یه مدلِ زبانی استفاده
می‌کنه، جمله‌های پیچیده/محاوره‌ای/طولانی رو خیلی طبیعی‌تر و دقیق‌تر ترجمه
می‌کنه.
"""
from telethon import events

from .. import ai, config
from ..config import PREFIX
from ..runtime import client
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from . import audio

_SYSTEM_PROMPT = (
    "شما دستیاری هستید که پیام‌های فارسی/انگلیسیِ تلگرام رو خلاصه یا تحلیل "
    "می‌کنه و به سوالات پاسخ می‌ده. کوتاه، دقیق و بدون مقدمه‌چینیِ اضافه پاسخ بده."
)


async def _ask_and_reply(event, messages, *, thinking_text="🤔 در حال فکر کردن..."):
    await event.edit(thinking_text)
    try:
        answer = await ai.ask_ai(messages)
    except ai.AIDisabledError:
        return await event.edit(
            "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
            "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن "
            "(اختیاری: `AI_MODEL`/`AI_API_BASE` برای سرویس‌های دیگه)."
        )
    except ai.AIRequestError as e:
        _record_error()
        return await event.edit(f"❌ خطا در ارتباط با سرویسِ هوش مصنوعی: {e}")
    if not answer:
        return await event.edit("⚠️ مدل پاسخِ خالی برگردوند")
    tagged_text, entities = ai.tag_ai_text(f"🤖 {answer}")
    await event.edit(tagged_text, formatting_entities=entities)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پرسش", "ask"])))
async def ask_handler(event):
    question = (event.pattern_match.group(1) or "").strip()
    context_text = None

    image_part = None  # 🖼 برای contextِ مولتی‌مدال
    if event.is_reply:
        reply = await event.get_reply_message()
        context_text = reply.raw_text or ""
        if reply.media and type(reply.media).__name__ == "MessageMediaPhoto":
            # 🖼 عکس → به‌عنوانِ بخشی از context (vision) کنارِ سوالِ کاربر
            await event.edit("🖼 در حال دیدنِ عکس...")
            try:
                import base64

                data = await reply.download_media(bytes)
                b64 = base64.b64encode(data).decode()
                image_part = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            except Exception as e:
                _record_error()
                return await event.edit(f"❌ خطا در دانلودِ عکس: {e}")
        elif not context_text and audio.is_audio_message(reply):
            # ریپلای‌شده صوتیه و متنِ مستقیم نداره؛ خودکار رونویسی می‌کنیم
            # تا `.پرسش`/`.پرسش <سوال>` روی پیامِ صوتی هم کار کنه.
            await event.edit("⏳ در حال رونویسیِ پیامِ صوتی...")
            try:
                context_text = await audio.transcribe_message(reply)
            except ai.AIDisabledError:
                return await event.edit(
                    "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
                    "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن."
                )
            except ai.AIRequestError as e:
                _record_error()
                return await event.edit(f"❌ خطا در رونویسیِ پیامِ صوتی: {e}")

    if not question and not context_text:
        return await event.edit(
            f"مثال: `{PREFIX}پرسش پایتخت فرانسه کجاست؟`\n"
            f"با ریپلای روی یه پیام (متنی یا صوتی): `{PREFIX}پرسش` برای خلاصه/تحلیلِ همون پیام، "
            f"یا `{PREFIX}پرسش این پیام چی میگه؟` برای سوال درباره‌ش."
        )

    # 🧠 سوال درباره‌ی گفتگوهای قبلیِ خودِ کاربر («آخرین باری که درباره‌ی ... صحبت کردم چی گفتیم؟»)
    # → جستجوی معنایی در پیام‌های ایندکس‌شده (نام/تاریخ/منبع/لینک). با ریپلای روی پیام، مسیرِ قبلی.
    if question and not event.is_reply:
        from . import semantic

        if await semantic.should_route(question):
            return await semantic.answer_recall(event, question)

    if context_text and question:
        user_content = f"متنِ زیر رو در نظر بگیر:\n\n{context_text}\n\nسوال: {question}"
    elif context_text:
        user_content = f"متنِ زیر رو خلاصه/تحلیل کن:\n\n{context_text}"
    else:
        user_content = question

    # 🤖 Agent Mode: اگر روشن باشد، Context Engine + Tool Calling اجرا می‌شود
    from ..storage.settings_toggles import toggles

    if toggles.get("agent_mode", False):
        await event.edit("🧠 عامل در حال فکر کردن و استفاده از ابزارها...")
        try:
            from .. import ai_agent

            ctx = await ai_agent.build_context(question or context_text or "")
            answer = await ai_agent.run_agent(user_content, context=ctx)
        except ai.AIDisabledError:
            return await event.edit(
                "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
                "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن."
            )
        except ai.AIRequestError as e:
            _record_error()
            return await event.edit(f"❌ خطا در ارتباط با سرویسِ هوش مصنوعی: {e}")
        if not answer:
            return await event.edit("⚠️ عامل پاسخِ خالی برگردوند")
        tagged_text, entities = ai.tag_ai_text(f"🤖 {answer}")
        return await event.edit(tagged_text, formatting_entities=entities)

    # 🎤 شخصیتِ فعال + 🧠 Context Engine: خاطراتِ مرتبط + کارهای باز (سبک)
    from ..ai_agent import get_personality, personality_system_block

    system_prompt = _SYSTEM_PROMPT + "\n" + personality_system_block(await get_personality())
    memory_block = await ai.build_memory_context(question or context_text or "")
    tasks_block = ""
    try:
        from ..repositories import tasks_repo as _tr

        opens = await _tr.list_tasks(done=False, limit=5)
        if opens:
            tasks_block = "\n📝 کارهای بازِ کاربر:\n" + "\n".join(
                f"- #{t['id']} {t['text'][:50]}" for t in opens
            )
    except Exception:
        pass
    if memory_block:
        system_prompt = _SYSTEM_PROMPT + "\n\n" + memory_block
    if tasks_block:
        system_prompt = system_prompt + tasks_block

    messages = [{"role": "system", "content": system_prompt}]
    if image_part:
        user_msg = {"role": "user", "content": [
            {"type": "text", "text": user_content},
            image_part,
        ]}
        messages.append(user_msg)
    else:
        messages.append({"role": "user", "content": user_content})
    await _ask_and_reply(event, messages)


_SUMMARY_DEFAULT_MESSAGES = 50


@client.on(events.NewMessage(outgoing=True, pattern=pat(["خلاصه", "summarize"])))
async def summarize_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    count = _SUMMARY_DEFAULT_MESSAGES
    if arg:
        if not arg.isdigit():
            return await event.edit(
                f"مثال: `{PREFIX}خلاصه 50` (تعدادِ پیام‌های آخرِ همین چت برای خلاصه‌سازی)"
            )
        count = max(1, min(int(arg), config.AI_SUMMARY_MAX_MESSAGES))

    await event.edit(f"📥 در حالِ جمع‌آوریِ {count} پیامِ آخر...")
    try:
        msgs = await client.get_messages(event.chat_id, limit=count)
    except Exception as e:
        _record_error()
        return await event.edit(f"❌ خطا در دریافتِ پیام‌ها: {e}")

    lines = []
    for m in reversed(msgs):
        if not m.raw_text:
            continue
        sender = m.sender
        name = (
            getattr(sender, "first_name", None)
            or getattr(sender, "title", None)
            or getattr(sender, "username", None)
            or "؟"
        )
        lines.append(f"{name}: {m.raw_text}")

    if not lines:
        return await event.edit("پیامِ متنیِ قابل‌خلاصه‌سازی‌ای پیدا نشد")

    transcript = "\n".join(lines)
    # سقفِ تقریبیِ کاراکتر برای جلوگیری از ارسالِ حجمِ خیلی زیاد به مدل (هزینه/تایم‌اوت)
    if len(transcript) > 12000:
        transcript = transcript[-12000:]

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "این‌ها آخرین پیام‌های یه گروه/چتِ تلگرام هستن (فرمتِ هر خط: "
                "`فرستنده: متن`). یه خلاصه‌ی کوتاه و مرتب از موضوعاتِ اصلیِ بحث بده:\n\n"
                + transcript
            ),
        },
    ]
    await _ask_and_reply(
        event, messages, thinking_text=f"🤔 در حالِ خلاصه‌سازیِ {len(lines)} پیام..."
    )


_TRANSLATE_SYSTEM = (
    "شما یه مترجمِ حرفه‌ای هستید. متنِ کاربر رو دقیق، طبیعی و روان به زبانِ "
    "مقصدی که کاربر مشخص کرده ترجمه کن. فقط و فقط خودِ ترجمه رو برگردون - "
    "بدون توضیح، بدون گیومه، بدون مقدمه‌چینی، بدون ذکرِ زبانِ مبدأ/مقصد."
)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ترجمه‌هوشمند", "aitr"])))
async def ai_translate_handler(event):
    """
    ترجمه با مدلِ زبانی (جدا از `.ترجمه`ی معمولی در tools.py). کندتره و
    نیازمندِ AI_API_KEY هست، ولی برای متن‌های محاوره‌ای/پیچیده/طولانی
    کیفیتِ خیلی بهتری می‌ده.
    """
    args = (event.pattern_match.group(1) or "").strip()
    lang, text = None, None
    if args and " " in args:
        lang, text = args.split(" ", 1)
    elif args and event.is_reply:
        lang = args.strip()
        reply = await event.get_reply_message()
        text = reply.raw_text or ""
        if not text and audio.is_audio_message(reply):
            await event.edit("⏳ در حال رونویسیِ پیامِ صوتی...")
            try:
                text = await audio.transcribe_message(reply)
            except ai.AIDisabledError:
                return await event.edit(
                    "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
                    "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن."
                )
            except ai.AIRequestError as e:
                _record_error()
                return await event.edit(f"❌ خطا در رونویسیِ پیامِ صوتی: {e}")

    if not lang or not text:
        return await event.edit(
            f"مثال: `{PREFIX}ترجمه‌هوشمند en سلام دنیا` یا با ریپلای (متنی یا صوتی): `{PREFIX}ترجمه‌هوشمند en`"
        )

    messages = [
        {"role": "system", "content": _TRANSLATE_SYSTEM},
        {"role": "user", "content": f"به زبانِ «{lang}» ترجمه کن:\n\n{text}"},
    ]

    await event.edit(f"🤔 در حال ترجمه به {lang}...")
    try:
        answer = await ai.ask_ai(messages)
    except ai.AIDisabledError:
        return await event.edit(
            "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
            "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن "
            "(اختیاری: `AI_MODEL`/`AI_API_BASE` برای سرویس‌های دیگه).\n"
            f"برای ترجمه‌ی معمولی (بدون نیاز به AI) از `{PREFIX}ترجمه` استفاده کن."
        )
    except ai.AIRequestError as e:
        _record_error()
        return await event.edit(f"❌ خطا در ارتباط با سرویسِ هوش مصنوعی: {e}")
    if not answer:
        return await event.edit("⚠️ مدل پاسخِ خالی برگردوند")
    tagged_text, entities = ai.tag_ai_text(f"🌐🤖 ترجمه‌ی هوشمند ({lang}):\n{answer}")
    await event.edit(tagged_text, formatting_entities=entities)

@client.on(events.NewMessage(outgoing=True, pattern=pat(["عامل", "agent"])))
async def agent_handler(event):
    """`.عامل روشن/خاموش/وضعیت` — AI Agent Mode برای `.پرسش` (Tool Calling + Context)."""
    from ..storage.settings_toggles import set_toggle, toggles

    arg = (event.pattern_match.group(1) or "").strip().lower()
    if arg in ("روشن", "on", "1"):
        await set_toggle("agent_mode", True)
        return await event.edit(
            "🧠 **عامل (Agent Mode) روشن شد**\n"
            "حالا `.پرسش <هرچی>` از Context Engine + ابزارها استفاده می‌کند:\n"
            "ثبتِ کار، جستجوی حافظه، لیستِ کارها، انجامِ کار"
        )
    if arg in ("خاموش", "off", "0"):
        await set_toggle("agent_mode", False)
        return await event.edit("🧠 عامل خاموش شد — `.پرسش` به حالتِ عادی برگشت")
    state = "🟢 روشن" if toggles.get("agent_mode", False) else "🔴 خاموش"
    await event.edit(
        "🧠 **عامل (AI Agent)**\n"
        f"وضعیت: {state}\n\n"
        f"`{PREFIX}عامل روشن/خاموش`\n\n"
        "در حالتِ روشن، `.پرسش` قبل از پاسخ:\n"
        "• Context Engine را می‌سازد (حافظه + کارها + یادداشت‌ها)\n"
        "• در صورتِ نیاز ابزار صدا می‌زند (ثبت/لیست/انجامِ کار، جستجوی حافظه)\n"
        "• مدلِ مناسب را بر اساسِ نیت انتخاب می‌کند (AI_MODEL_FAST/CODING/REASONING)"
    )

@client.on(events.NewMessage(outgoing=True, pattern=pat(["شخصیت", "personality"])))
async def personality_handler(event):
    """`.شخصیت` — نمایش؛ `.شخصیت <نامِ preset>` — انتخاب؛ `.شخصیت سفارشی <متن>`"""
    from ..ai_agent import PERSONALITY_PRESETS, get_personality, set_personality

    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        cur = await get_personality()
        return await event.edit(
            "🎭 **شخصیتِ AI**\n\n"
            f"فعلی: {cur}\n\n"
            "پیش‌فرض‌ها: " + " • ".join(PERSONALITY_PRESETS) + "\n"
            f"`{PREFIX}شخصیت <نام>` برای انتخاب، یا `{PREFIX}شخصیت سفارشی <توضیح>`"
        )
    if arg.startswith("سفارشی"):
        custom = arg[len("سفارشی"):].strip()
        if not custom:
            return await event.edit("مثال: `.شخصیت سفارشی دستیارِ فنیِ خلاصه‌گو باش`")
        await set_personality(custom)
        return await event.edit(f"🎭 شخصیتِ سفارشی ذخیره شد: {custom}")
    if arg in PERSONALITY_PRESETS:
        await set_personality(PERSONALITY_PRESETS[arg])
        return await event.edit(f"🎭 شخصیت روی **{arg}** تنظیم شد.")
    await set_personality(arg)
    await event.edit(f"🎭 شخصیتِ سفارشی ذخیره شد: {arg}")
