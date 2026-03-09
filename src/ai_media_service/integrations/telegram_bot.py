"""
Telegram integration.

Flow:
  1. After content generation, notify_admin() sends the content to admin
     with Approve / Reject inline buttons.
  2. Admin clicks a button → callback handler updates DB qa_status.
  3. If approved → publish_to_channel() posts to the channel.

Run the bot listener as a separate process:
    python -m src.ai_media_service.integrations.telegram_bot
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ..config import settings
from ..database import get_session
from ..db_models import ContentItemDB

log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_bot() -> Bot:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    return Bot(token=settings.TELEGRAM_BOT_TOKEN)


def _approval_keyboard(content_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve", callback_data=f"approve:{content_id}"),
        InlineKeyboardButton(text="❌ Reject",  callback_data=f"reject:{content_id}"),
    ]])


# ── Sync wrappers (called from sync Chief pipeline) ──────────────────────────

_NICHE_NAMES = {
    "ai_business":    "Нейро Бизнес",
    "personal_brand": "Виден всем",
    "finance":        "Деньги просто",
}


def notify_admin(content_id: int, niche_key: str, topic: str, preview: str) -> None:
    """Отправляет запрос на апрув админу с кнопками ✅/❌."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        log.warning("Telegram не настроен — пропускаю уведомление")
        return

    niche_title = _NICHE_NAMES.get(niche_key, niche_key)

    import html as _html
    safe_topic = _html.escape(topic)
    safe_preview = _html.escape(preview[:800])
    safe_niche = _html.escape(niche_title)

    async def _send() -> None:
        bot = _make_bot()
        text = (
            f"📝 <b>Новый контент на проверку</b>\n\n"
            f"<b>Канал:</b> {safe_niche}\n"
            f"<b>Тема:</b> {safe_topic}\n\n"
            f"<b>Превью статьи:</b>\n{safe_preview}…\n\n"
            f"ID контента: <code>{content_id}</code>"
        )
        await bot.send_message(
            chat_id=settings.TELEGRAM_ADMIN_CHAT_ID,
            text=text,
            parse_mode="HTML",
            reply_markup=_approval_keyboard(content_id),
        )
        await bot.session.close()

    asyncio.run(_send())
    log.info("Админ уведомлён о content_id=%d (ниша=%s)", content_id, niche_key)


def publish_to_channel(content_id: int) -> bool:
    """Публикует одобренный контент в нужный Telegram-канал по нише."""
    if not settings.TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN не задан — пропускаю публикацию")
        return False

    with get_session() as session:
        item = session.get(ContentItemDB, content_id)
        if not item or item.qa_status != "approved":
            log.warning("Контент %d не найден или не одобрен", content_id)
            return False
        niche_key: str = item.niche_key
        posts: list[str] = item.telegram_posts or []

    channel_id = settings.channel_for(niche_key)
    if not channel_id:
        log.warning("Channel ID для ниши '%s' не задан в .env", niche_key)
        return False

    async def _post() -> None:
        bot = _make_bot()
        for post in posts:
            await bot.send_message(chat_id=channel_id, text=post)
            await asyncio.sleep(2)  # против флуд-лимита
        await bot.session.close()

    asyncio.run(_post())
    log.info("Опубликовано %d постов в канал '%s' (content_id=%d)", len(posts), niche_key, content_id)
    return True


# ── Bot listener (runs as a long-lived process) ───────────────────────────────

dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 AI Media Service bot.\n"
        "I'll send you content for approval — just click Approve or Reject."
    )


@dp.callback_query(F.data.startswith("approve:"))
async def cb_approve(call: CallbackQuery) -> None:
    content_id = int(call.data.split(":")[1])
    _update_qa_status(content_id, "approved")
    await call.answer("✅ Approved!")
    await call.message.edit_text(
        call.message.html_text + f"\n\n✅ <b>Approved</b> — posting to channel...",
        parse_mode="HTML",
    )
    posted = publish_to_channel(content_id)
    if posted:
        await call.message.answer(f"📢 Content {content_id} posted to channel.")
    else:
        await call.message.answer(f"⚠️ Could not post content {content_id} to channel.")


@dp.callback_query(F.data.startswith("reject:"))
async def cb_reject(call: CallbackQuery) -> None:
    content_id = int(call.data.split(":")[1])
    _update_qa_status(content_id, "rejected")
    await call.answer("❌ Rejected")
    await call.message.edit_text(
        call.message.html_text + "\n\n❌ <b>Rejected</b>",
        parse_mode="HTML",
    )


def _update_qa_status(content_id: int, status: str) -> None:
    with get_session() as session:
        item = session.get(ContentItemDB, content_id)
        if item:
            item.qa_status = status
            session.commit()
            log.info("content_id=%d → qa_status=%s", content_id, status)


async def _run_bot() -> None:
    bot = _make_bot()
    log.info("Telegram bot polling started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    from ..logging_config import setup_logging
    from ..database import init_db

    setup_logging()
    init_db()
    asyncio.run(_run_bot())
