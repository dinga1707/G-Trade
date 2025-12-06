"""
main.py

Entry point for the Telegram-based Dhan index options trading system.

How to run:
    python main.py --config config.json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Dict

from aiogram import Bot, Dispatcher

from config import AppConfig, DhanAccountConfig, load_config
from dhan_client import DhanClient
from instrument_resolver import InstrumentResolver
from notifications import TelegramNotifier
from telegram_bot import setup_telegram_handlers
from trading_service import TradingService


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def build_dhan_clients(cfg: AppConfig) -> Dict[str, DhanClient]:
    clients: Dict[str, DhanClient] = {}
    for acc in cfg.dhan_accounts:
        clients[acc.name] = DhanClient(
            name=acc.name,
            client_id=acc.client_id,
            access_token=acc.access_token,
        )
    return clients


async def main_async(config_path: str) -> None:
    setup_logging()
    logger = logging.getLogger("main")

    cfg: AppConfig = load_config(config_path)

    if not cfg.instruments_csv_path:
        raise ValueError(
            "instruments_csv_path missing in config.json. "
            "Provide a CSV path or replace InstrumentResolver implementation."
        )

    resolver = InstrumentResolver(csv_path=cfg.instruments_csv_path)

    dhan_clients = build_dhan_clients(cfg)

    bot = Bot(token=cfg.telegram_bot_token, parse_mode="HTML")
    notifier = TelegramNotifier(bot)

    trading_service = TradingService(
        config=cfg,
        dhan_clients=dhan_clients,
        resolver=resolver,
        notifier=notifier,
    )

    dp = Dispatcher()
    setup_telegram_handlers(dp, cfg, trading_service, notifier)

    logger.info("Starting Telegram polling...")
    await dp.start_polling(bot)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram Dhan Trading Bot")
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to config JSON file (default: config.json)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main_async(args.config))
