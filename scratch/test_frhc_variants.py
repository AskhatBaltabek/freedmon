import cloudscraper
from bs4 import BeautifulSoup

def test_frhc_variants():
    scraper = cloudscraper.create_scraper()
    variants = [
        "https://www.investing.com/equities/freedom-holding-corp",
        "https://www.investing.com/equities/freedom-holding",
        "https://www.investing.com/equities/freedom-holding-corp-inc",
        "https://www.investing.com/equities/frhc"
    ]
    for url in variants:
        print(f"Testing {url}...")
        resp = scraper.get(url, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            last = soup.select_one('[data-test="instrument-price-last"]')
            print(f"  Last Price: {last.text if last else 'Selector failed'}")
            break

if __name__ == "__main__":
    test_frhc_variants()
