import schedule
import time
import asyncio
import os
from db import init_db, save_equities, save_currency, save_ocr
from scraper import fetch_frhc_data, fetch_usd_kzt
from vision import capture_snapshot, extract_freedom_price
from datetime import datetime

async def job():
    print(f"\n--- Starting Monitoring Cycle at {datetime.now()} ---")
    
    # 1. Scrape FRHC
    print("Scraping FRHC data...")
    frhc_data = await fetch_frhc_data()
    if frhc_data:
        print(f"FRHC: Live={frhc_data['live_price']}, Pre={frhc_data['pre_market']}, Post={frhc_data['post_market']}")
        save_equities(frhc_data['pre_market'], frhc_data['post_market'], frhc_data['live_price'])
    else:
        print("Failed to scrape FRHC data.")
    
    # 2. Scrape USD/KZT
    print("Scraping USD/KZT rate...")
    usd_kzt = await fetch_usd_kzt()
    if usd_kzt:
        print(f"USD/KZT: {usd_kzt}")
        save_currency(usd_kzt)
    else:
        print("Failed to scrape USD/KZT data.")
    
    # 3. Camera & OCR
    print("Capturing snapshot...")
    snapshot_path = capture_snapshot()
    if snapshot_path:
        print(f"Snapshot saved: {snapshot_path}")
        ocr_price = extract_freedom_price(snapshot_path)
        if ocr_price:
            print(f"OCR Extracted Price: {ocr_price}")
            save_ocr(ocr_price, snapshot_path)
        else:
            print("OCR failed to extract price.")
    else:
        print("Camera capture failed.")

    print(f"--- Cycle Complete at {datetime.now()} ---")

def run_async_job():
    asyncio.run(job())

if __name__ == "__main__":
    # Initialize DB
    init_db()
    
    print("Freedom Finance Monitoring App Started.")
    print("Running every 1 minutes...")
    
    # Run once at startup
    run_async_job()
    
    # Schedule every 2 minutes
    schedule.every(1).minutes.do(run_async_job)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitoring app stopped.")
