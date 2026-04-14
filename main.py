import schedule
import time
import asyncio
import os
import cv2
import pytesseract
import re
import requests
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

from db import init_db, save_equities, save_currency, save_ocr, save_calculation
from scraper import fetch_frhc_data, fetch_usd_kzt
from vision import capture_snapshot, extract_freedom_price
from datetime import datetime

# Set Tesseract path since it's installed but not in system PATH
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def send_telegram_alert(message, chat_id):
    token = os.environ.get("TG_BOT_TOKEN")
    if not token or not chat_id:
        print(f"Telegram configuration missing (Token: {bool(token)}, Chat ID: {chat_id}). Cannot send alert.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        if response.status_code != 200:
            print(f"Failed to send Telegram alert: {response.text}")
        else:
            print(f"Telegram alert sent successfully to {chat_id}.")
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")



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
    ocr_price = None
    if snapshot_path:
        print(f"Snapshot saved: {snapshot_path}")
        
        # Crop the image based on coordinates
        img = cv2.imread(snapshot_path)
        if img is not None:
            # Crop using [y1:y2, x1:x2]
            # y1 = 1865, y2 = 1935, x1 = 280, x2 = 472
            cropped = img[1865:1935, 280:472]
            
            if cropped.size == 0:
                print(f"Error: Cropped image is empty! Original image shape: {img.shape}. Check if camera disconnected or screen rotated.")
            else:
                # Save cropped image primarily for debugging
                cropped_path = snapshot_path.replace(".png", "_cropped.png").replace(".jpg", "_cropped.jpg")
                cv2.imwrite(cropped_path, cropped)
                print(f"Cropped image saved to: {cropped_path}")
                
                # OCR directly from cropped
                gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
                try:
                    # Use page segmentation mode 7 (Treat the image as a single text line)
                    text = pytesseract.image_to_string(gray, config='--psm 7').strip()
                    print(f"OCR Raw Text: {text}")
                    
                    # Keep just digits, commas, dots
                    clean_text = text.replace(' ', '').replace(',', '.')
                    match = re.search(r"(\d+\.\d+|\d+)", clean_text)
                    if match:
                        ocr_price = float(match.group(1))
                        print(f"OCR Extracted Price: {ocr_price}")
                        save_ocr(ocr_price, snapshot_path)
                    else:
                        print("OCR failed to extract price from cropped image.")
                except Exception as e:
                    print(f"OCR Error: {e}")
        else:
            print("Failed to load snapshot for cropping.")
    else:
        print("Camera capture failed.")

    # 4. Math and Comparisons
    if frhc_data and usd_kzt:
        live = frhc_data.get('live_price')
        pre = frhc_data.get('pre_market')
        post = frhc_data.get('post_market')
        
        # Determine which price to use and track the source (Priority: Pre -> Post -> Live)
        equities_price = None
        price_source = "N/A"
        
        if pre is not None:
            equities_price = pre
            price_source = "Pre"
        elif post is not None:
            equities_price = post
            price_source = "Post"
        elif live is not None:
            equities_price = live
            price_source = "Live"
        
        if equities_price is not None:
            calculated_rate = (usd_kzt * equities_price) / 10000
            print(f"Calculated Rate: {calculated_rate} ({price_source} {equities_price} * USD/KZT {usd_kzt} / 10000)")
            
            diff_pct = None
            if ocr_price is not None:
                # Calculate percent difference compared to calculated_rate
                # Formula: abs(ocr - calc) / calc * 100
                diff_pct = abs(ocr_price - calculated_rate) / calculated_rate * 100
                print(f"Difference: {diff_pct:.2f}%")
            
            # Save to database
            save_calculation(calculated_rate, ocr_price, diff_pct)
            
            # Send Telegram alert if difference >= 1.0%
            if diff_pct is not None and diff_pct >= 1.0:
                print(f"Difference ({diff_pct:.2f}%) exceeds 1.0%, sending Telegram alert...")
                
                # Determine signal and target chat ID
                if ocr_price < calculated_rate:
                    signal = "🟢 *ЗЕЛЕНЫЙ СИГНАЛ (КУПИТЬ)*"
                    target_chat_id = os.environ.get("TG_CHAT_ID_BUY")
                elif ocr_price > calculated_rate:
                    signal = "🔴 *КРАСНЫЙ СИГНАЛ (ПРОДАТЬ)*"
                    target_chat_id = os.environ.get("TG_CHAT_ID_SELL")
                else:
                    signal = "⚪ *НЕЙТРАЛЬНО*"
                    target_chat_id = os.environ.get("TG_CHAT_ID_BUY")

                msg = (
                    f"{signal}\n\n"
                    "🚨 *Freedom Arbitrage Alert* 🚨\n\n"
                    f"📈 FRHC ({price_source}): `{equities_price:.2f}` $\n"
                    f"💱 USD/KZT (Yahoo): `{usd_kzt:.2f}` ₸\n\n"
                    f"🧮 Calculated Rate: `{calculated_rate:.4f}`\n"
                    f"📷 Extracted Rate: `{ocr_price:.4f}`\n"
                    f"⚠️ Difference: *{diff_pct:.2f}%*"
                )
                send_telegram_alert(msg, target_chat_id)
        else:
            print("No valid equities price found to perform calculation.")
    else:
        print("Missing required data (FRHC or USD/KZT) to perform calculation.")

    print(f"--- Cycle Complete at {datetime.now()} ---")

def run_async_job():
    asyncio.run(job())

def cleanup_snapshots():
    print(f"\n--- Cleaning up snapshots folder at {datetime.now()} ---")
    folder = "snapshots"
    if os.path.exists(folder):
        count = 0
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    count += 1
            except Exception as e:
                print(f"Error deleting file {filepath}: {e}")
        print(f"Deleted {count} files from {folder}.")

if __name__ == "__main__":
    # Initialize DB
    init_db()
    
    print("Freedom Finance Monitoring App Started.")
    print("Running every 1 minutes...")
    print("Snapshots cleanup scheduled every 1 hour.")
    
    # Run once at startup
    run_async_job()
    
    # Schedule every 1 minute
    schedule.every(1).minutes.do(run_async_job)
    
    # Schedule snapshot cleanup every 1 hour
    schedule.every(1).hours.do(cleanup_snapshots)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitoring app stopped.")
