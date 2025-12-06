"""
monitor.py

Price monitoring loop that drives the strategy and triggers exits via callbacks.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from models import TradeContext
from strategy import TradeStrategy
from notifications import Notifier

logger = logging.getLogger(__name__)


class PriceMonitor:
    """
    Monitors LTP for a single trade context & strategy.

    - get_ltp: async callable that returns float
    - on_exit: async callback taking (trade_context, exit_reason)
    """

    def __init__(
        self,
        trade_context: TradeContext,
        strategy: TradeStrategy,
        get_ltp: Callable[[], Awaitable[float]],
        notifier: Notifier,
        chat_id: int,
        poll_interval_sec: float,
        on_exit: Callable[[TradeContext, str], Awaitable[None]],
    ) -> None:
        self._trade_context = trade_context
        self._strategy = strategy
        self._get_ltp = get_ltp
        self._notifier = notifier
        self._chat_id = chat_id
        self._poll_interval_sec = poll_interval_sec
        self._on_exit = on_exit
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info(
            "Starting monitor for %s (trade_id=%s)",
            self._trade_context.instrument.trading_symbol,
            self._trade_context.trade_id,
        )

        try:
            while self._running and not self._strategy.is_finished:
                price = await self._get_ltp()
                event = self._strategy.on_price_tick(price)

                # Send intermediate notifications (target hit, trailing start, etc.)
                for note in event.notifications:
                    await self._notifier.send_message(self._chat_id, note)

                if event.exit_now and event.exit_reason:
                    await self._on_exit(self._trade_context, event.exit_reason)
                    break

                await asyncio.sleep(self._poll_interval_sec)
        except Exception as exc:
            logger.exception(
                "Error in monitor loop for trade_id=%s: %s",
                self._trade_context.trade_id,
                exc,
            )
            await self._notifier.send_message(
                self._chat_id,
                f"⚠️ Error in price monitor for {self._trade_context.instrument.trading_symbol}: {exc}",
            )
        finally:
            logger.info(
                "Monitor stopped for trade_id=%s", self._trade_context.trade_id
            )
            self._running = False
