"""
trading_service.py

Coordinates:
- instrument resolution
- multi-account order placement (async)
- creation of strategies & monitors
- exit orders on SL / trailing SL hit
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List

from config import AppConfig, DhanAccountConfig
from dhan_client import DhanClient
from instrument_resolver import InstrumentResolver, InstrumentNotFoundError
from models import (
    AccountPosition,
    Instrument,
    Side,
    TradeCommand,
    TradeContext,
)
from monitor import PriceMonitor
from notifications import Notifier
from strategy import TradeStrategy

logger = logging.getLogger(__name__)


class TradingService:
    def __init__(
        self,
        config: AppConfig,
        dhan_clients: Dict[str, DhanClient],
        resolver: InstrumentResolver,
        notifier: Notifier,
    ) -> None:
        self._config = config
        self._clients = dhan_clients
        self._resolver = resolver
        self._notifier = notifier
        self._active_monitors: Dict[str, asyncio.Task] = {}

        master_name = config.master_account.name
        if master_name not in self._clients:
            raise ValueError(f"Master account '{master_name}' has no DhanClient instance.")
        self._master_client = self._clients[master_name]

    async def handle_trade_command(self, cmd: TradeCommand, chat_id: int) -> None:
        """
        Entry point from Telegram for a parsed TradeCommand.
        """
        try:
            instrument = self._resolver.resolve(
                symbol=cmd.symbol,
                expiry=cmd.expiry,
                strike=cmd.strike,
                option_type=cmd.option_type,
            )
        except InstrumentNotFoundError as e:
            await self._notifier.send_message(chat_id, f"❌ {e}")
            return

        trade_id = self._build_trade_id(cmd)
        logger.info("Starting new trade: %s", trade_id)

        await self._notifier.send_message(
            chat_id,
            (
                f"📥 New trade request: {cmd.side.value} {cmd.symbol} {cmd.expiry} "
                f"{cmd.strike} {cmd.option_type.value}\n"
                f"Instrument: {instrument.trading_symbol}\nTrade ID: {trade_id}"
            ),
        )

        positions = await self._place_orders_for_all_accounts(cmd, instrument, chat_id, trade_id)
        if not positions:
            await self._notifier.send_message(chat_id, "❌ All orders failed; no position open.")
            return

        trade_ctx = TradeContext(
            command=cmd,
            instrument=instrument,
            positions=positions,
            chat_id=chat_id,
            trade_id=trade_id,
        )

        # Use master account entry price to seed the strategy
        master_pos = positions.get(self._config.master_account.name)
        if master_pos is None:
            # Fallback: use average across all positions
            avg_entry = sum(p.avg_price for p in positions.values()) / len(positions)
        else:
            avg_entry = master_pos.avg_price

        strategy = TradeStrategy(side=cmd.side, entry_price=avg_entry)

        poll_interval_sec = self._config.price_poll_interval_ms / 1000.0

        async def get_ltp() -> float:
            return await self._master_client.get_ltp(instrument)

        monitor = PriceMonitor(
            trade_context=trade_ctx,
            strategy=strategy,
            get_ltp=get_ltp,
            notifier=self._notifier,
            chat_id=chat_id,
            poll_interval_sec=poll_interval_sec,
            on_exit=self._on_exit_triggered,
        )

        task = asyncio.create_task(monitor.run(), name=f"monitor-{trade_id}")
        self._active_monitors[trade_id] = task
        await self._notifier.send_message(
            chat_id,
            (
                f"📡 Started monitoring {instrument.trading_symbol} at entry {avg_entry:.2f} "
                f"(poll every {poll_interval_sec:.3f}s)."
            ),
        )

    async def _place_orders_for_all_accounts(
        self,
        cmd: TradeCommand,
        instrument: Instrument,
        chat_id: int,
        trade_id: str,
    ) -> Dict[str, AccountPosition]:
        """
        Place market orders across all enabled accounts concurrently.

        Returns dict of AccountPosition for successful accounts.
        """
        tasks = []
        account_cfgs: List[DhanAccountConfig] = []

        for acc_cfg in self._config.dhan_accounts:
            if not acc_cfg.enabled_for_trading:
                continue
            client = self._clients.get(acc_cfg.name)
            if client is None:
                logger.error("No DhanClient for account '%s'", acc_cfg.name)
                continue

            qty = int(self._config.base_quantity * acc_cfg.multiplier)
            if qty <= 0:
                logger.warning(
                    "Skipping account '%s' due to non-positive quantity %s",
                    acc_cfg.name,
                    qty,
                )
                continue

            account_cfgs.append(acc_cfg)
            tasks.append(
                asyncio.create_task(
                    self._place_single_order(client, acc_cfg, cmd.side, instrument, qty, trade_id)
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        positions: Dict[str, AccountPosition] = {}
        lines = ["🧾 Order summary:"]

        for acc_cfg, res in zip(account_cfgs, results):
            if isinstance(res, Exception):
                logger.exception(
                    "Order failed for account '%s': %s", acc_cfg.name, res
                )
                lines.append(f"❌ {acc_cfg.name}: {res}")
                continue

            # res = (order_id, avg_price, quantity)
            order_id, avg_price, qty = res
            pos = AccountPosition(
                account_name=acc_cfg.name,
                quantity=qty,
                avg_price=avg_price,
                side=cmd.side,
                order_id=order_id,
                is_open=True,
            )
            positions[acc_cfg.name] = pos
            lines.append(
                f"✅ {acc_cfg.name}: qty={qty}, avg={avg_price:.2f}, order_id={order_id}"
            )

        if positions:
            lines.append(f"Total successful accounts: {len(positions)}")
        msg = "\n".join(lines)
        await self._notifier.send_message(chat_id, msg)

        return positions

    async def _place_single_order(
        self,
        client: DhanClient,
        acc_cfg: DhanAccountConfig,
        side: Side,
        instrument: Instrument,
        qty: int,
        trade_id: str,
    ):
        """
        Place a single market order and fetch its average price.
        """
        logger.info(
            "Placing order for trade_id=%s, account=%s, side=%s, qty=%s",
            trade_id,
            acc_cfg.name,
            side,
            qty,
        )
        order_resp = await client.place_market_order(instrument, side, qty)

        # Adjust according to Dhan response structure
        order_id = str(order_resp.get("order_id") or order_resp.get("id"))
        if not order_id:
            raise RuntimeError(f"Missing order_id in Dhan response: {order_resp}")

        # Some brokers give avg price in the response; if not, fetch via order_status
        avg_price = order_resp.get("average_price")
        if avg_price is None:
            avg_price = await client.get_order_average_price(order_id)
        else:
            avg_price = float(avg_price)

        logger.info(
            "Order placed: trade_id=%s, account=%s, order_id=%s, avg_price=%.2f",
            trade_id,
            acc_cfg.name,
            order_id,
            avg_price,
        )
        return order_id, avg_price, qty

    async def _on_exit_triggered(self, trade_ctx: TradeContext, reason: str) -> None:
        """
        Called by monitor when SL / trailing SL is hit.
        """
        logger.info(
            "Exit triggered for trade_id=%s, reason=%s",
            trade_ctx.trade_id,
            reason,
        )
        await self._notifier.send_message(
            trade_ctx.chat_id,
            (
                f"🚪 Exit triggered for {trade_ctx.instrument.trading_symbol}: {reason}. "
                f"Exiting all accounts at market..."
            ),
        )

        tasks = []
        for acc_name, pos in trade_ctx.positions.items():
            if not pos.is_open or pos.quantity <= 0:
                continue
            client = self._clients.get(acc_name)
            if client is None:
                logger.error("No DhanClient for account '%s' on exit.", acc_name)
                continue

            tasks.append(
                asyncio.create_task(
                    self._exit_single_position(client, trade_ctx, pos, reason)
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        lines = ["🧾 Exit summary:"]
        for acc_name, res in zip(trade_ctx.positions.keys(), results):
            if isinstance(res, Exception):
                lines.append(f"❌ {acc_name}: {res}")
            else:
                lines.append(f"✅ {acc_name}: exit order placed ({res})")

        await self._notifier.send_message(trade_ctx.chat_id, "\n".join(lines))

    async def _exit_single_position(
        self,
        client: DhanClient,
        trade_ctx: TradeContext,
        pos: AccountPosition,
        reason: str,
    ):
        """
        Exit a single account position at market (opposite side).
        """
        logger.info(
            "Exit position: trade_id=%s, account=%s, qty=%s, reason=%s",
            trade_ctx.trade_id,
            pos.account_name,
            pos.quantity,
            reason,
        )
        resp = await client.exit_market_order(
            instrument=trade_ctx.instrument,
            side=pos.side,
            quantity=pos.quantity,
        )
        pos.is_open = False
        return resp

    @staticmethod
    def _build_trade_id(cmd: TradeCommand) -> str:
        return (
            f"{cmd.symbol}-{cmd.expiry}-{cmd.strike}-{cmd.option_type.value}-"
            f"{cmd.side.value}"
        )
