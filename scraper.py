import asyncio
import yfinance as yf
import cloudscraper
from bs4 import BeautifulSoup
import re

async def fetch_frhc_investing():
    """Fetches FRHC data from Investing.com."""
    try:
        url = "https://www.investing.com/equities/freedom"
        scraper = cloudscraper.create_scraper()
        
        print("Fetching FRHC data via Investing.com...")
        resp = await asyncio.to_thread(scraper.get, url, timeout=10)
        
        if resp.status_code != 200:
            print(f"Investing.com FRHC failed (Status {resp.status_code})")
            return None
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Selectors based on data-test attributes (standard for Investing.com)
        last_el = soup.select_one('[data-test="instrument-price-last"]')
        pre_el = soup.select_one('[data-test="instrument-price-pre-market"]')
        post_el = soup.select_one('[data-test="instrument-price-post-market"]')
        
        if not last_el:
            print("Investing.com FRHC: Main price element not found.")
            return None
            
        def clean_float(text):
            return float(text.replace(',', '')) if text else None

        data = {
            "live_price": clean_float(last_el.text),
            "closing_price": clean_float(last_el.text), # Assuming last is closing if market is closed
            "pre_market": clean_float(pre_el.text) if pre_el else None,
            "post_market": clean_float(post_el.text) if post_el else None,
            "volume": None, # Complex to parse from Investing.com quickly
            "high": None,
            "low": None
        }
        
        print(f"FRHC Investing: {data}")
        return data
        
    except Exception as e:
        print(f"Error fetching FRHC via Investing.com: {e}")
        return None

async def fetch_frhc_yahoo():
    """Fetches FRHC data using the yfinance library (Fallback)."""
    try:
        print("Fetching FRHC data via yfinance (Fallback)...")
        ticker = await asyncio.to_thread(yf.Ticker, "FRHC")
        info = await asyncio.to_thread(lambda: ticker.info)
        
        live_price = info.get("regularMarketPrice")
        pre_market = info.get("preMarketPrice")
        post_market = info.get("postMarketPrice")
        closing_price = live_price
        
        # New data points
        volume = info.get("regularMarketVolume") or info.get("volume")
        high = info.get("regularMarketDayHigh") or info.get("dayHigh")
        low = info.get("regularMarketDayLow") or info.get("dayLow")
        
        if live_price is None:
            fast_info = ticker.fast_info
            live_price = fast_info.get("last_price")
            closing_price = live_price
            
        return {
            "live_price": live_price,
            "closing_price": closing_price,
            "pre_market": pre_market,
            "post_market": post_market,
            "volume": volume,
            "high": high,
            "low": low
        }
    except Exception as e:
        print(f"Error fetching FRHC via yfinance: {e}")
        return None

async def fetch_frhc_data():
    """Primary: Investing.com, Fallback: yfinance."""
    data = await fetch_frhc_investing()
    if data:
        return data
    return await fetch_frhc_yahoo()

async def fetch_usd_kzt_investing():
    """Fetches USD/KZT rate from Investing.com."""
    try:
        url = "https://www.investing.com/currencies/usd-kzt"
        scraper = cloudscraper.create_scraper()
        
        print("Fetching USD/KZT via Investing.com...")
        resp = await asyncio.to_thread(scraper.get, url, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            last_el = soup.select_one('[data-test="instrument-price-last"]')
            if last_el:
                rate = float(last_el.text.replace(',', ''))
                print(f"USD/KZT Investing: {rate}")
                return rate
        return None
    except Exception as e:
        print(f"Error fetching USD/KZT via Investing.com: {e}")
        return None

async def fetch_usd_kzt_yahoo():
    """Fetches USD/KZT rate via yfinance (Fallback)."""
    try:
        print("Fetching USD/KZT rate via yfinance (Fallback)...")
        ticker = await asyncio.to_thread(yf.Ticker, "USDKZT=X")
        info = await asyncio.to_thread(lambda: ticker.info)
        rate = info.get("regularMarketPrice")
        
        if rate is None:
            fast_info = ticker.fast_info
            rate = fast_info.get("last_price")
        return rate
    except Exception as e:
        print(f"Error fetching USD/KZT via yfinance: {e}")
        return None

async def fetch_usd_kzt():
    """Primary: Investing.com, Fallback: yfinance."""
    rate = await fetch_usd_kzt_investing()
    if rate:
        return rate
    return await fetch_usd_kzt_yahoo()

if __name__ == "__main__":
    import json
    async def test():
        print("Testing yfinance Scraper...")
        frhc = await fetch_frhc_data()
        print(f"FRHC Result: {json.dumps(frhc, indent=2)}")
        usd = await fetch_usd_kzt()
        print(f"USD/KZT Result: {usd}")
    asyncio.run(test())
