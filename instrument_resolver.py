"""
instrument_resolver.py

InstrumentResolver maps (symbol, expiry, strike, option_type) to a concrete Instrument.

This version uses a local CSV. You can later replace the implementation to use
Dhan's master data / instrument lookup APIs without changing the interface.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

from models import Instrument, OptionType

logger = logging.getLogger(__name__)


class InstrumentNotFoundError(Exception):
    pass


@dataclass
class InstrumentResolver:
    """
    CSV columns expected (you can adapt):

    symbol,expiry,strike,option_type,security_id,trading_symbol,segment

    Example row:
    BANKNIFTY,27FEB2025,48500,CE,123456,BANKNIFTY27FEB25C48500,NSE_FNO
    """
    csv_path: Path

    def __post_init__(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Instruments CSV not found: {self.csv_path}")

        self._rows: List[dict] = []
        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._rows.append(row)

        logger.info("Loaded %d instruments from %s", len(self._rows), self.csv_path)

    def resolve(
        self,
        symbol: str,
        expiry: str,
        strike: int,
        option_type: OptionType,
    ) -> Instrument:
        symbol = symbol.upper()
        expiry = expiry.upper()
        opt = option_type.value.upper()

        for row in self._rows:
            if (
                row["symbol"].upper() == symbol
                and row["expiry"].upper() == expiry
                and int(row["strike"]) == strike
                and row["option_type"].upper() == opt
            ):
                return Instrument(
                    security_id=row["security_id"],
                    trading_symbol=row["trading_symbol"],
                    symbol=symbol,
                    expiry=expiry,
                    strike=strike,
                    option_type=option_type,
                    segment=row.get("segment", "NSE_FNO"),
                )

        raise InstrumentNotFoundError(
            f"Instrument not found for {symbol} {expiry} {strike} {opt}"
        )
