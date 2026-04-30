#!/usr/bin/env python3
"""
Debug script to check Investing.com HTML and find correct selectors for price elements.
"""

import asyncio
import cloudscraper
from bs4 import BeautifulSoup

async def check_investing_selectors():
    """Fetches the page and tests various selectors."""
    url = "https://www.investing.com/equities/freedom"
    scraper = cloudscraper.create_scraper()
    
    print(f"Fetching {url}...")
    resp = await asyncio.to_thread(scraper.get, url, timeout=10)
    
    if resp.status_code != 200:
        print(f"Failed to fetch (Status {resp.status_code})")
        return
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    print("\n" + "="*80)
    print("TESTING SELECTORS")
    print("="*80)
    
    # Test primary selectors
    selectors = {
        'Main (data-test="instrument-price-last")': '[data-test="instrument-price-last"]',
        'Pre-market (data-test="instrument-price-pre-market")': '[data-test="instrument-price-pre-market"]',
        'Post-market (data-test="instrument-price-post-market")': '[data-test="instrument-price-post-market"]',
        'All span with data-test': 'span[data-test]',
    }
    
    for name, selector in selectors.items():
        elements = soup.select(selector)
        print(f"\n{name}:")
        print(f"  Selector: {selector}")
        print(f"  Found: {len(elements)} element(s)")
        for i, el in enumerate(elements[:3]):  # Show first 3
            print(f"    [{i}] Text: '{el.text.strip()}' | HTML: {str(el)[:100]}...")
    
    # Try to find all price-related elements
    print("\n" + "="*80)
    print("SEARCHING FOR PRICE ELEMENTS")
    print("="*80)
    
    # Look for patterns
    patterns = [
        ('Contains "162" or similar', lambda el: el.text.strip() and any(c in el.text for c in '0123456789')),
        ('Has class containing "price"', lambda el: el.get('class') and any('price' in c.lower() for c in el.get('class', []))),
    ]
    
    for pattern_name, pattern_func in patterns:
        spans = soup.find_all('span', limit=200)
        matches = [el for el in spans if pattern_func(el)]
        print(f"\n{pattern_name}: {len(matches)} matches")
        for i, el in enumerate(matches[:5]):
            attrs = ' | '.join([f"{k}='{v}'" for k, v in el.attrs.items() if k != 'class'])
            print(f"  [{i}] Text: '{el.text.strip()}' | {attrs}")

if __name__ == "__main__":
    asyncio.run(check_investing_selectors())
