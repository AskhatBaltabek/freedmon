import asyncio
import yfinance as yf

async def fetch_frhc_data():
    """Fetches FRHC data using the yfinance library."""
    try:
        print("Fetching FRHC data via yfinance...")
        # yfinance is blocking, so we run it in a thread to keep it async-friendly
        ticker = await asyncio.to_thread(yf.Ticker, "FRHC")
        info = await asyncio.to_thread(lambda: ticker.info)
        
        # Extract prices
        live_price = info.get("regularMarketPrice")
        pre_market = info.get("preMarketPrice")
        post_market = info.get("postMarketPrice")
        
        # Fallback if ticker.info is sparse (sometimes happens with yfinance)
        if live_price is None:
            fast_info = ticker.fast_info
            live_price = fast_info.get("last_price")
            
        print(f"FRHC yfinance: Live={live_price}, Pre={pre_market}, Post={post_market}")
        
        return {
            "live_price": live_price,
            "pre_market": pre_market,
            "post_market": post_market
        }
    except Exception as e:
        print(f"Error fetching FRHC via yfinance: {e}")
        return None

async def fetch_usd_kzt():
    """Fetches USD/KZT rate using the yfinance library."""
    try:
        print("Fetching USD/KZT rate via yfinance...")
        ticker = await asyncio.to_thread(yf.Ticker, "USDKZT=X")
        # For currencies, fast_info or regularMarketPrice works
        info = await asyncio.to_thread(lambda: ticker.info)
        rate = info.get("regularMarketPrice")
        
        if rate is None:
            fast_info = ticker.fast_info
            rate = fast_info.get("last_price")
            
        if rate:
            print(f"USD/KZT yfinance: {rate}")
        return rate
    except Exception as e:
        print(f"Error fetching USD/KZT via yfinance: {e}")
        return None

if __name__ == "__main__":
    import json
    async def test():
        print("Testing yfinance Scraper...")
        frhc = await fetch_frhc_data()
        print(f"FRHC Result: {json.dumps(frhc, indent=2)}")
        usd = await fetch_usd_kzt()
        print(f"USD/KZT Result: {usd}")
    asyncio.run(test())
