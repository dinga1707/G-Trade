"""
parser.py

Parses plain text Telegram commands into structured TradeCommand objects.

Expected format:

BUY BANKNIFTY 27FEB2025 48500 CE
SELL NIFTY 27FEB2025 22500 PE
"""

from __future__ import annotations

from models import Side, OptionType, TradeCommand


class CommandParseError(Exception):
    pass


def parse_trade_command(text: str) -> TradeCommand:
    parts = text.strip().upper().split()
    if len(parts) < 5:
        raise CommandParseError(
            "Invalid format. Expected: 'BUY|SELL SYMBOL EXPIRY STRIKE CE|PE'. "
            "Example: BUY BANKNIFTY 27FEB2025 48500 CE"
        )

    action, symbol, expiry, strike_str, opt_type_str = parts[:5]

    if action not in ("BUY", "SELL"):
        raise CommandParseError("Action must be BUY or SELL.")

    if opt_type_str not in ("CE", "PE"):
        raise CommandParseError("Option type must be CE or PE.")

    try:
        strike = int(strike_str)
    except ValueError:
        raise CommandParseError("Strike must be an integer, e.g., 48500")

    side = Side(action)
    opt_type = OptionType(opt_type_str)

    return TradeCommand(
        side=side,
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        option_type=opt_type,
    )
