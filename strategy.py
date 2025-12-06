"""
strategy.py

Encapsulates target / stop-loss / trailing stop-loss logic.

Implements a state machine over price ticks for a single trade.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from models import Side, TradePhase, StrategyEvent

logger = logging.getLogger(__name__)


@dataclass
class TradeStrategy:
    side: Side
    entry_price: float
    phase: TradePhase = TradePhase.BEFORE_TARGET
    target: float = field(init=False)
    stop_loss: float = field(init=False)

    trailing_ref_price: Optional[float] = None  # highest/lowest in trailing
    is_finished: bool = False
    exit_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.side == Side.BUY:
            self.target = self.entry_price + 25
            self.stop_loss = self.entry_price - 20
        else:
            self.target = self.entry_price - 25
            self.stop_loss = self.entry_price + 20

        logger.info(
            "Initialized strategy: side=%s, entry=%.2f, target=%.2f, SL=%.2f",
            self.side,
            self.entry_price,
            self.target,
            self.stop_loss,
        )

    def on_price_tick(self, price: float) -> StrategyEvent:
        """
        Process a new price tick and update state.

        Returns a StrategyEvent describing actions & notifications.
        """
        if self.is_finished:
            # Already exited
            return StrategyEvent()

        if self.side == Side.BUY:
            return self._handle_buy(price)
        else:
            return self._handle_sell(price)

    # --- BUY LOGIC ---------------------------------------------------------

    def _handle_buy(self, price: float) -> StrategyEvent:
        event = StrategyEvent()
        logger.debug(
            "BUY tick: price=%.2f, phase=%s, target=%.2f, SL=%.2f",
            price,
            self.phase,
            self.target,
            self.stop_loss,
        )

        # Global SL check applies in all non-exited phases
        if price <= self.stop_loss:
            self.is_finished = True
            reason = "STOPLOSS HIT" if self.phase == TradePhase.BEFORE_TARGET else "TRAILING SL HIT"
            self.exit_reason = reason
            event.exit_now = True
            event.exit_reason = reason
            event.notifications.append(f"Exit BUY: {reason} at price {price:.2f}")
            return event

        if self.phase == TradePhase.BEFORE_TARGET:
            # Check if initial target hit
            if price >= self.target:
                self.phase = TradePhase.AFTER_TARGET
                # Move SL to target - 7
                self.stop_loss = self.target - 7
                msg = (
                    f"Target hit for BUY at {price:.2f}. "
                    f"Moving SL to {self.stop_loss:.2f} (target - 7)."
                )
                event.notifications.append(msg)
                return event

        elif self.phase == TradePhase.AFTER_TARGET:
            # Check if price extends 5 points beyond target -> enable trailing
            if price >= self.target + 5:
                self.phase = TradePhase.TRAILING
                self.trailing_ref_price = price
                self.stop_loss = self.trailing_ref_price - 5
                msg =(
                    f"Switching to trailing mode for BUY. "
                    f"Start price {price:.2f}, SL set to {self.stop_loss:.2f} (current - 5)."
                )
                event.notifications.append(msg)
                return event

        elif self.phase == TradePhase.TRAILING:
            # Update trailing high
            if self.trailing_ref_price is None or price > self.trailing_ref_price:
                self.trailing_ref_price = price
                self.stop_loss = self.trailing_ref_price - 5
                event.notifications.append(
                    f"New high {price:.2f}. Trailing SL updated to {self.stop_loss:.2f}."
                )

        return event

    # --- SELL LOGIC --------------------------------------------------------

    def _handle_sell(self, price: float) -> StrategyEvent:
        event = StrategyEvent()
        logger.debug(
            "SELL tick: price=%.2f, phase=%s, target=%.2f, SL=%.2f",
            price,
            self.phase,
            self.target,
            self.stop_loss,
        )

        # Global SL check
        if price >= self.stop_loss:
            self.is_finished = True
            reason = "STOPLOSS HIT" if self.phase == TradePhase.BEFORE_TARGET else "TRAILING SL HIT"
            self.exit_reason = reason
            event.exit_now = True
            event.exit_reason = reason
            event.notifications.append(f"Exit SELL: {reason} at price {price:.2f}")
            return event

        if self.phase == TradePhase.BEFORE_TARGET:
            # Target hit
            if price <= self.target:
                self.phase = TradePhase.AFTER_TARGET
                self.stop_loss = self.target + 7
                msg = (
                    f"Target hit for SELL at {price:.2f}. "
                    f"Moving SL to {self.stop_loss:.2f} (target + 7)."
                )
                event.notifications.append(msg)
                return event

        elif self.phase == TradePhase.AFTER_TARGET:
            # Beyond target by 5 points
            if price <= self.target - 5:
                self.phase = TradePhase.TRAILING
                self.trailing_ref_price = price
                self.stop_loss = self.trailing_ref_price + 5
                msg = (
                    f"Switching to trailing mode for SELL. "
                    f"Start price {price:.2f}, SL set to {self.stop_loss:.2f} (current + 5)."
                )
                event.notifications.append(msg)
                return event

        elif self.phase == TradePhase.TRAILING:
            if self.trailing_ref_price is None or price < self.trailing_ref_price:
                self.trailing_ref_price = price
                self.stop_loss = self.trailing_ref_price + 5
                event.notifications.append(
                    f"New low {price:.2f}. Trailing SL updated to {self.stop_loss:.2f}."
                )

        return event
