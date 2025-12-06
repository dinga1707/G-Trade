"""
telegram_bot.py

Sets up the Telegram bot using aiogram, parses messages, and forwards
valid commands to TradingService.
"""

from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.types import Message

from config import AppConfig
from notifications import Notifier
from parser import parse_trade_command, CommandParseError
from trading_service import TradingService

logger = logging.getLogger(__name__)


def setup_telegram_handlers(
    dp: Dispatcher,
    config: AppConfig,
    trading_service: TradingService,
    notifier: Notifier,
) -> None:
    """
    Registers message handlers on the dispatcher.
    """

    @dp.message()
    async def handle_message(message: Message) -> None:
        chat_id = message.chat.id

        # Allow only configured chats
        if chat_id not in config.telegram_allowed_chat_ids:
            logger.info("Ignoring message from unauthorized chat_id=%s", chat_id)
            return

        if not message.text:
            return

        text = message.text.strip()
        logger.info("Received message from chat %s: %s", chat_id, text)

        # Allow "ping" / simple health check
        if text.lower() in ("/start", "/help"):
            await notifier.send_message(
                chat_id,
                (
                    "👋 Telegram Trading Bot is online.\n"
                    "Send commands like:\n"
                    "BUY BANKNIFTY 27FEB2025 48500 CE\n"
                    "SELL NIFTY 27FEB2025 22500 PE"
                ),
            )
            return

        try:
            cmd = parse_trade_command(text)
        except CommandParseError as e:
            await notifier.send_message(chat_id, f"❌ {e}")
            return

        await trading_service.handle_trade_command(cmd, chat_id)
