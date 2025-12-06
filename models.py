"""
models.py

Core shared models & enums.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"


@dataclass
class TradeCommand:
    side: Side
    symbol: str          # e.g., NIFTY, BANKNIFTY
    expiry: str          # e.g., 27FEB2025
    strike: int          # e.g., 48500
    option_type: OptionType  # CE / PE


@dataclass
class Instrument:
    security_id: str
    trading_symbol: str
    symbol: str
    expiry: str
    strike: int
    option_type: OptionType
    segment: str = "NSE_FNO"  # default; adjust to Dhan nomenclature


class TradePhase(str, Enum):
    BEFORE_TARGET = "BEFORE_TARGET"
    AFTER_TARGET = "AFTER_TARGET"
    TRAILING = "TRAILING"
    EXITED = "EXITED"


@dataclass
class StrategyEvent:
    """
    Result of processing a price tick.
    """
    exit_now: bool = False
    exit_reason: Optional[str] = None  # e.g., "STOPLOSS HIT", "TRAILING SL HIT"
    notifications: list[str] | None = None

    def __post_init__(self) -> None:
        if self.notifications is None:
            self.notifications = []


@dataclass
class AccountPosition:
    account_name: str
    quantity: int
    avg_price: float
    side: Side
    order_id: str
    is_open: bool = True


@dataclass
class TradeContext:
    command: TradeCommand
    instrument: Instrument
    positions: dict[str, AccountPosition]  # key = account name
    chat_id: int
    trade_id: str  # simple identifier for logs (e.g., "BANKNIFTY-27FEB2025-48500-CE-BUY")
