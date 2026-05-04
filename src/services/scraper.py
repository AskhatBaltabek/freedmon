import asyncio
import yfinance as yf
import cloudscraper
from bs4 import BeautifulSoup
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ScraperService:
    """Service handling financial data scraping from various sources."""
    
    @staticmethod
    async def fetch_frhc_investing() -> Optional[Dict[str, Any]]:
        """
        Fetches Freedom Holding Corp. (FRHC) stock prices from Investing.com using a cloudscraper.
        
        It attempts to parse the HTML to extract:
        - Live/Last Price
        - Pre-Market Price
        - Post-Market (After Hours) Price
        
        Returns:
            dict: A dictionary containing the extracted prices, or None if the request/parsing fails.
        """
        try:
            url = "https://www.investing.com/equities/freedom"
            scraper = cloudscraper.create_scraper()
            
            logger.info("Fetching FRHC data via Investing.com...")
            resp = await asyncio.to_thread(scraper.get, url, timeout=10)
            
            if resp.status_code != 200:
                logger.warning(f"Investing.com FRHC failed (Status {resp.status_code})")
                return None
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            def clean_float(text):
                if not text:
                    return None
                # Remove common currency/percent symbols and whitespace
                cleaned = text.replace(',', '').replace('$', '').replace('%', '').replace('+', '').strip()
                try:
                    return float(cleaned)
                except ValueError:
                    return None
            
            live_price = None
            pre_market = None
            post_market = None
            
            # NEW APPROACH: Find prices based on Investing.com's actual HTML structure
            # Look for sections with "Pre Market" and "Post Market" labels
            
            # Find Pre Market price
            pre_links = soup.find_all('a', href=lambda h: h and 'pre-market' in h.lower())
            if not pre_links:
                pre_links = soup.find_all('a', string=lambda s: s and ('pre market' in s.lower() or 'pre-market' in s.lower()))
            
            for pre_link in pre_links:
                # The price is in a span with class "order-2" after the link
                parent = pre_link.parent.parent
                if parent:
                    price_span = parent.find('span', class_=lambda x: x and 'order-2' in x)
                    if price_span:
                        pre_market = clean_float(price_span.text)
                        logger.info(f"Found pre-market price: {pre_market}")
                        break
            
            # Find Post Market price (now often labeled "After Hours")
            post_links = soup.find_all('a', href=lambda h: h and 'after-hours' in h.lower())
            if not post_links:
                post_links = soup.find_all('a', string=lambda s: s and ('post market' in s.lower() or 'after hours' in s.lower()))
            
            for post_link in post_links:
                parent = post_link.parent.parent
                if parent:
                    price_span = parent.find('span', class_=lambda x: x and 'order-2' in x)
                    if price_span:
                        post_market = clean_float(price_span.text)
                        logger.info(f"Found after-hours price: {post_market}")
                        break
            
            # Find Live/Last price - usually first price section with numeric value
            all_price_sections = soup.find_all(['span', 'div'], class_=lambda x: x and 'text-base' in x)
            for section in all_price_sections[:20]:
                price = clean_float(section.text)
                if price and 150 < price < 200 and price not in [pre_market, post_market]:
                    live_price = price
                    logger.info(f"Found live/last price: {live_price}")
                    break
            
            # Fallback: if still no live price, try the old method
            if not live_price:
                logger.debug("Trying fallback selector for live price...")
                last_el = soup.select_one('[data-test="instrument-price-last"]')
                if last_el:
                    live_price = clean_float(last_el.text)
            
            logger.info(f"Investing.com fetched - Live: {live_price}, Pre: {pre_market}, Post: {post_market}")
            
            data = {
                "live_price": live_price,
                "closing_price": live_price,
                "pre_market": pre_market,
                "post_market": post_market,
                "volume": None, 
                "high": None,
                "low": None
            }
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching FRHC via Investing.com: {e}")
            return None

    @staticmethod
    async def fetch_frhc_yahoo() -> Optional[Dict[str, Any]]:
        """
        Fetches FRHC data using the yfinance library. 
        This acts as a fallback mechanism if Investing.com scraping fails.
        
        Returns:
            dict: A dictionary containing regular, pre-market, and post-market prices, or None on failure.
        """
        try:
            logger.info("Fetching FRHC data via yfinance (Fallback)...")
            ticker = await asyncio.to_thread(yf.Ticker, "FRHC")
            info = await asyncio.to_thread(lambda: ticker.info)
            
            live_price = info.get("regularMarketPrice")
            pre_market = info.get("preMarketPrice")
            post_market = info.get("postMarketPrice")
            closing_price = live_price
            
            volume = info.get("regularMarketVolume") or info.get("volume")
            high = info.get("regularMarketDayHigh") or info.get("dayHigh")
            low = info.get("regularMarketDayLow") or info.get("dayLow")
            
            if live_price is None:
                fast_info = ticker.fast_info
                live_price = fast_info.get("last_price")
                closing_price = live_price
            
            result = {
                "live_price": live_price,
                "closing_price": closing_price,
                "pre_market": pre_market,
                "post_market": post_market,
                "volume": volume,
                "high": high,
                "low": low
            }
            
            logger.info(f"Yahoo Finance data - Live: {live_price}, Pre: {pre_market}, Post: {post_market}")
            return result
        except Exception as e:
            logger.error(f"Error fetching FRHC via yfinance: {e}")
            return None

    @classmethod
    async def fetch_frhc_data(cls) -> Optional[Dict[str, Any]]:
        """
        Primary interface to fetch FRHC market data.
        
        Strategy:
        1. Attempt to scrape from Investing.com (Primary).
        2. If that fails or returns None, fallback to yfinance.
        
        Returns:
            dict | None: The compiled market data dictionary.
        """
        data = await cls.fetch_frhc_investing()
        if data:
            return data
        return await cls.fetch_frhc_yahoo()

    @staticmethod
    async def fetch_usd_kzt_investing() -> Optional[float]:
        """
        Fetches the current USD to KZT exchange rate from Investing.com.
        
        Returns:
            float: The exchange rate, or None if the request/parsing fails.
        """
        try:
            url = "https://www.investing.com/currencies/usd-kzt"
            scraper = cloudscraper.create_scraper()
            
            logger.info("Fetching USD/KZT via Investing.com...")
            resp = await asyncio.to_thread(scraper.get, url, timeout=10)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                last_el = soup.select_one('[data-test="instrument-price-last"]')
                if last_el:
                    return float(last_el.text.replace(',', ''))
            return None
        except Exception as e:
            logger.error(f"Error fetching USD/KZT via Investing.com: {e}")
            return None

    @staticmethod
    async def fetch_usd_kzt_yahoo() -> Optional[float]:
        """
        Fetches the USD to KZT exchange rate via yfinance.
        Acts as a fallback if the Investing.com scraper fails.
        
        Returns:
            float: The exchange rate, or None on failure.
        """
        try:
            logger.info("Fetching USD/KZT rate via yfinance (Fallback)...")
            ticker = await asyncio.to_thread(yf.Ticker, "USDKZT=X")
            info = await asyncio.to_thread(lambda: ticker.info)
            rate = info.get("regularMarketPrice")
            
            if rate is None:
                fast_info = ticker.fast_info
                rate = fast_info.get("last_price")
            return rate
        except Exception as e:
            logger.error(f"Error fetching USD/KZT via yfinance: {e}")
            return None

    @classmethod
    async def fetch_usd_kzt(cls) -> Optional[float]:
        """
        Primary interface to fetch the USD/KZT exchange rate.
        
        Strategy:
        1. Attempt Investing.com (Primary).
        2. Fallback to yfinance.
        
        Returns:
            float | None: The exchange rate.
        """
        rate = await cls.fetch_usd_kzt_investing()
        if rate:
            return rate
        return await cls.fetch_usd_kzt_yahoo()
