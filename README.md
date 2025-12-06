# G-Trade
Smart trading bot with telegram 

Trade via Telegram
Example commands:

BUY BANKNIFTY 27FEB2025 48500 CE
SELL NIFTY 27FEB2025 22500 PE


Multi-account trading (Async)
Each account has multipliers, flags, and independent order placement.

Automated Strategy Logic

BUY: Target = +25, SL = –20

SELL: Target = –25, SL = +20

After target: SL shifts (±7)

After extension: Trailing SL (5 points)

Real-time LTP monitoring 

telegram_dhan_bot_full/
│
├── README.md
├── requirements.txt
├── config.json
├── instruments.csv
│
├── core/
│   ├── config.py
│   ├── models.py
│   ├── parser.py
│   ├── dhan_client.py
│   ├── instrument_resolver.py
│   ├── strategy.py
│   ├── monitor.py
│   ├── notifications.py
│   ├── trading_service.py
│
├── bot/
│   ├── telegram_bot.py
│
├── app/
│   ├── main.py
│
└── tests/
    ├── test_strategy.py

Generated folder structure.
