"""
notifications.py

Abstractions for sending notifications (Telegram, logs, etc.).
"""

from __future__ import annotations

from typing import Protocol

from aiogram import Bot


class Notifier(Protocol):
    async def send_message(self, chat_id: int, text: str) -> None: ...


class TelegramNotifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_message(self, chat_id: int, text: str) -> None:
        await self._bot.send_message(chat_id=chat_id, text=text)
