# LLM Project Guideline: Freedmon Bot

This document provides a concise overview of the Freedmon project to help other LLMs understand the architecture and logic quickly while minimizing token usage.

## 🎯 Project Goal
A trading bot that monitors price discrepancies (arbitrage) between:
1.  **Freedom Finance Mobile App**: Real-time price extracted via OCR (Tesseract) from Android screenshots (ADB).
2.  **Market Sources (Yahoo Finance/FRHC)**: Live/Pre/Post-market prices scraped via `ScraperService`.

## 📂 Key Architecture
- `src/main.py`: Main entry point. Contains the `monitoring_cycle` (every 30s) and time-based logic.
- `src/core/config.py`: Centralized configuration (thresholds, chat IDs, paths).
- `src/services/vision_service.py`: Handles ADB connections, screenshots, and OCR price extraction.
- `src/services/scraper.py`: Fetches external market data (FRHC, USD/KZT).
- `src/services/notifier.py`: Sends Telegram notifications with HTML formatting.
- `src/database/repository.py`: SQLite wrapper. Manages signal history, subscriber list, and price caches.

## 🕒 Important Time Logic
The bot operates across two primary timezones:
- **New York (America/New_York)**: Determines Market status (Open: 09:30-16:00, Pre: 04:00-09:30, Post: 16:00-20:00).
- **Astana (Asia/Almaty, UTC+5)**: Used for Night Monitoring.

## 🛡️ Key Signal Rules
- **Night Window (01:00 – 05:00 Astana)**: All standard arbitrage signals are suppressed. Only **Volatility Signals** (`_check_night_volatility_signal`) are sent to subscribers.
- **Duplicate Prevention**: Consecutive identical signals (same type and similar rates) are suppressed to avoid spamming Telegram.
- **Market Fallbacks**: Uses cached Pre/Post market prices if live data is unavailable during those sessions.

## 🛠️ Tech Stack
- **Language**: Python (Asyncio)
- **OCR**: Tesseract + OpenCV
- **Database**: SQLite
- **Communication**: Telegram Bot API
- **Device Control**: ADB over WiFi

## 💡 Analysis Tips for LLMs
- When analyzing logic, prioritize `monitoring_cycle` in `src/main.py` as it orchestrates all services.
- Check `src/database/repository.py` for query logic and duplicate detection implementation.
- Use `Config` class from `src/core/config.py` to understand environment variables.
