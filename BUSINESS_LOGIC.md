# Freedmon Business Logic

This document details the core rules and calculations driving the Freedmon arbitrage bot.

## 1. Core Arbitrage Calculation
The system identifies arbitrage opportunities between the local Kazakhstani Freedom Finance mobile app and the US NASDAQ market.

**Formula:**
`Calculated Rate = (FRHC_Price * USD_KZT_Rate) / 10000`

- `FRHC_Price`: The stock price of Freedom Holding Corp. (in USD).
- `USD_KZT_Rate`: The USD to KZT exchange rate.
- `10000`: A normalization factor specific to the Freedom App's internal conversion display.

The bot compares the `Calculated Rate` against the `OCR Extracted Rate` (the price read directly from the Freedom Finance app screen via Tesseract OCR).

**Alert Trigger:**
If `abs(OCR_Rate - Calculated_Rate) / Calculated_Rate * 100 >= Config.DIFFERENCE_THRESHOLD_PERCENT` (default 1.0%), a signal is generated.

## 2. Market Session Fallbacks (New York Time)
The `FRHC_Price` used in the calculation depends on the current NASDAQ market session (based on NY time `America/New_York`):

- **Market Open (09:30 - 16:00)**: Uses the **Live** price. Pre/Post-market caches are explicitly cleared.
- **Pre-Market (04:00 - 09:30)**: 
  - Attempts to scrape fresh Pre-market data.
  - If unavailable, uses the **Cached Pre-Market** price.
  - If cache is empty, falls back to **Cached Post-Market** price from the previous day.
  - Final fallback: Live price.
- **Post-Market (16:00 - 04:00 next day)** (and weekends): 
  - Pre-market cache is explicitly cleared at 16:00.
  - Attempts to scrape fresh Post-market data.
  - If unavailable, uses the **Cached Post-Market** price.
  - Final fallback: Live price (closing price).

## 3. The "Night Window" (Astana Time)
Between **01:00 and 05:00** Astana Time (`Asia/Almaty`), the Freedom Finance platform experiences distinct behavior. Standard arbitrage signals are considered noisy and are **suppressed**.

Instead, two specific "Night" mechanics take over:

1. **Night Baseline Capture**: At exactly 01:00, the first successfully OCR'd price is saved to the database as the `night_baseline_price`.
2. **Standard Night Suppression**: Any regular arbitrage signal calculated against the NY market is logged but *not sent* to Telegram.
3. **Volatility Signals (Only sent during night)**: The bot continuously compares the current OCR price against the *previous cycle's* OCR price (approx. every 20 seconds).
   - If the price jumps by **> 0.8%** between consecutive cycles, a "Volatility Spike" alert is sent to all subscribers.

## 4. Anti-Spam & Rate Limiting
To prevent flooding the Telegram channel:

- **Duplicate Signal Suppression**: Before sending a Buy/Sell signal, the bot checks the `signals` database table. If a signal of the *same type* (e.g., GREEN) with the exact same OCR and Calculated rates was sent recently, the new signal is dropped.
- **Error Rate Limiting**: If an exception occurs during a task (e.g., Scraper timeout) or an OCR bounding box warning triggers, the error is sent to the admin chat (`TG_CHAT_ID_ERROR`). However, to prevent spam, these notifications are hard-limited to a maximum of **once every 30 minutes** per error type.
