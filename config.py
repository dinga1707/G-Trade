"""
config.py

Configuration loading and validation.

Reads from a JSON file (e.g., config.json) and exposes strongly-typed
dataclasses to the rest of the system.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


logger = logging.getLogger(__name__)


@dataclass
class DhanAccountConfig:
    name: str
    client_id: str
    access_token: str
    is_master: bool
    enabled_for_trading: bool
    multiplier: float = 1.0


@dataclass
class AppConfig:
    telegram_bot_token: str
    telegram_allowed_chat_ids: List[int]
    dhan_accounts: List[DhanAccountConfig]
    base_quantity: int
    price_poll_interval_ms: int = 500
    instruments_csv_path: Optional[str] = None  # Optional, for CSV-based resolver

    @property
    def master_account(self) -> DhanAccountConfig:
        masters = [acc for acc in self.dhan_accounts if acc.is_master]
        if not masters:
            raise ValueError("No master Dhan account configured")
        if len(masters) > 1:
            raise ValueError("More than one master Dhan account configured")
        return masters[0]


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    dhan_accounts = [
        DhanAccountConfig(
            name=a["name"],
            client_id=a["client_id"],
            access_token=a["access_token"],
            is_master=a.get("is_master", False),
            enabled_for_trading=a.get("enabled_for_trading", True),
            multiplier=float(a.get("multiplier", 1)),
        )
        for a in raw["dhan_accounts"]
    ]

    cfg = AppConfig(
        telegram_bot_token=raw["telegram_bot_token"],
        telegram_allowed_chat_ids=[int(cid) for cid in raw["telegram_allowed_chat_ids"]],
        dhan_accounts=dhan_accounts,
        base_quantity=int(raw["base_quantity"]),
        price_poll_interval_ms=int(raw.get("price_poll_interval_ms", 500)),
        instruments_csv_path=raw.get("instruments_csv_path"),
    )

    logger.info("Configuration loaded from %s", path)
    return cfg
