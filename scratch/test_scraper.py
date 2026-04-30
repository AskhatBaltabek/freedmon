import cloudscraper
from bs4 import BeautifulSoup
import re

def test_investing():
    scraper = cloudscraper.create_scraper()
    
    # Test FRHC
    print("Testing FRHC Scaling...")
    url_frhc = "https://www.investing.com/equities/freedom-holding-corp"
    resp = scraper.get(url_frhc)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Check for price selectors
        # They often use data-test attributes
        last = soup.select_one('[data-test="instrument-price-last"]')
        pre = soup.select_one('[data-test="instrument-price-pre-market"]')
        post = soup.select_one('[data-test="instrument-price-post-market"]')
        
        print(f"FRHC Status: 200")
        print(f"Last Price Element: {last.text if last else 'Not found'}")
        print(f"Pre-Market Element: {pre.text if pre else 'Not found'}")
        print(f"Post-Market Element: {post.text if post else 'Not found'}")
    else:
        print(f"FRHC Failed with status: {resp.status_code}")

    # Test USD/KZT
    print("\nTesting USD/KZT Scaling...")
    url_usd = "https://www.investing.com/currencies/usd-kzt"
    resp = scraper.get(url_usd)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'html.parser')
        last = soup.select_one('[data-test="instrument-price-last"]')
        print(f"USD/KZT Status: 200")
        print(f"Last Price Element: {last.text if last else 'Not found'}")
    else:
        print(f"USD/KZT Failed with status: {resp.status_code}")

if __name__ == "__main__":
    test_investing()
