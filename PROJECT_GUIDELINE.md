# LLM Project Guideline: Freedmon Bot

This document provides a concise overview of the Freedmon project to help developers and LLMs understand the architecture quickly while minimizing token usage.

## 🎯 Project Goal
A trading bot that monitors price discrepancies (arbitrage) between:
1.  **Freedom Finance Mobile App**: Real-time price extracted via OCR (Tesseract) from Android screenshots (via ADB over WiFi).
2.  **Market Sources (Yahoo Finance / Investing.com)**: Live/Pre/Post-market prices for the FRHC ticker scraped via `ScraperService`.

The system compares the OCR rate against the calculated rate `(FRHC * USD/KZT) / 10000` and alerts Telegram subscribers if the difference exceeds a configured threshold.

## 📂 Architecture (Clean Architecture)
The project is modularized under the `src/` directory:

- `main.py` (Root): Simple entry point that catches fatal errors and runs the async event loop.
- `src/main.py`: The task scheduler. Uses `asyncio` to run concurrent cycles (monitoring, post-market, cleanup).
- `src/controllers/monitoring_controller.py`: The brain of the bot. Orchestrates the `monitoring_cycle`, handling data fetching, OCR parsing, math comparisons, signal generation, and routing.
- `src/services/night_service.py`: Encapsulates logic for the Astana night-window (01:00-05:00), baseline capturing, and volatility signal detection.
- `src/services/vision_service.py`: Manages ADB connections, screenshot capture, and OCR logic.
- `src/services/scraper.py`: Fetches external market data (FRHC, USD/KZT) using BeautifulSoup and `yfinance` fallbacks.
- `src/services/notifier.py`: Manages Telegram API communications.
- `src/core/time_utils.py`: Centralized timezone (Astana/New York) and market session logic.
- `src/core/config.py`: Centralized configuration loaded from `.env`.
- `src/database/repository.py`: SQLite wrapper for persistence, signal history, and subscriber management.

## 🔗 Business Logic Reference
For detailed explanations of the arbitrage formula, market session fallbacks, and anti-spam mechanisms, please refer to [BUSINESS_LOGIC.md](BUSINESS_LOGIC.md).

## 💡 Analysis Tips for LLMs
- **Entry Point**: Look at `src/controllers/monitoring_controller.py` to understand the step-by-step flow of a standard monitoring cycle.
- **Time/State**: If the bot is behaving differently based on the time of day, check `src/core/time_utils.py` and `src/services/night_service.py`.
- **Database/Duplicates**: Check `src/database/repository.py` for how duplicate signals are prevented before being sent to Telegram.
