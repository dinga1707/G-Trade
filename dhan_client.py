"""
dhan_client.py

Thin async wrapper around the Dhan Python SDK.

All SDK calls are assumed to be blocking, so we execute them via asyncio.to_thread
to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict

from models import Instrument, Side

logger = logging.getLogger(__name__)

try:
    from dhanhq import dhanhq  # type: ignore
except ImportError:  # pragma: no cover - user will install the SDK
    dhanhq = None


@dataclass
class DhanClient:
    name: str
    client_id: str
    access_token: str

    def __post_init__(self) -> None:
        if dhanhq is None:
            logger.warning("dhanhq SDK not installed. Install via `pip install dhanhq`.")
            self._client = None
        else:
            # Adjust ctor to match actual sdk
            self._client = dhanhq(self.client_id, self.access_token)

    async def place_market_order(
        self,
        instrument: Instrument,
        side: Side,
        quantity: int,
        product_type: str = "INTRADAY",  # adjust to Dhan
        validity: str = "DAY",
    ) -> Dict[str, Any]:
        """
        Place a market order for the given account & instrument.

        Returns the raw order response from Dhan, expected to contain
        order_id and average price (or use a follow-up API call).
        """
        if self._client is None:
            raise RuntimeError("Dhan client not initialized (SDK missing).")

        def _place() -> Dict[str, Any]:
            # TODO: Map correctly to Dhan SDK parameters.
            # The below is pseudocode; adjust fields to real SDK.
            logger.info(
                "Placing market order: account=%s, side=%s, symbol=%s, qty=%s",
                self.name,
                side,
                instrument.trading_symbol,
                quantity,
            )
            order_response = self._client.place_order(
                security_id=instrument.security_id,
                exchange_segment=instrument.segment,
                transaction_type=side.value,
                quantity=quantity,
                order_type="MARKET",
                product_type=product_type,
                validity=validity,
            )
            return order_response

        return await asyncio.to_thread(_place)

    async def exit_market_order(
        self,
        instrument: Instrument,
        side: Side,
        quantity: int,
        product_type: str = "INTRADAY",
        validity: str = "DAY",
    ) -> Dict[str, Any]:
        """
        Exit an existing position by placing a market order in the opposite direction.
        """
        opposite_side = Side.BUY if side == Side.SELL else Side.SELL
        return await self.place_market_order(
            instrument=instrument,
            side=opposite_side,
            quantity=quantity,
            product_type=product_type,
            validity=validity,
        )

    async def get_ltp(self, instrument: Instrument) -> float:
        """
        Fetch LTP (Last Traded Price) for the given instrument.

        You may use the Dhan quote API here.
        """
        if self._client is None:
            raise RuntimeError("Dhan client not initialized (SDK missing).")

        def _get() -> float:
            # TODO: adjust to actual Dhan quote/ltp API.
            logger.debug(
                "Fetching LTP: account=%s, symbol=%s",
                self.name,
                instrument.trading_symbol,
            )
            quote = self._client.get_instrument_quote(instrument.segment, instrument.security_id)
            # Example: quote["last_traded_price"]
            ltp = float(quote["last_traded_price"])
            return ltp

        return await asyncio.to_thread(_get)

    async def get_order_average_price(self, order_id: str) -> float:
        """
        Fetch the average filled price for an order.

        This might require calling an order-status endpoint in the Dhan SDK.
        """
        if self._client is None:
            raise RuntimeError("Dhan client not initialized (SDK missing).")

        def _get() -> float:
            # TODO: adjust to actual Dhan order details API.
            logger.debug("Fetching order avg price: account=%s, order_id=%s", self.name, order_id)
            info = self._client.get_order(order_id)
            avg_price = float(info["average_price"])
            return avg_price

        return await asyncio.to_thread(_get)
