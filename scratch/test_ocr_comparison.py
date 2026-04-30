import cv2
import pytesseract
import os
import sys

# Add the project root to sys.path to import vision
project_root = r"c:\Users\User\Desktop\work\freedmon"
if project_root not in sys.path:
    sys.path.append(project_root)

from vision import extract_freedom_price, preprocess_image

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def old_ocr_logic(img):
    """Mirroring the old logic from main.py"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    try:
        text = pytesseract.image_to_string(gray, config='--psm 7').strip()
        return text
    except:
        return "ERROR"

def test_ocr_comparison(image_path):
    if not os.path.exists(image_path):
        return

    img = cv2.imread(image_path)
    if img is None:
        return

    print(f"\n--- Testing: {os.path.basename(image_path)} ---")
    
    # Old
    old_raw = old_ocr_logic(img)
    
    # New
    new_price = extract_freedom_price(img)
    
    print(f"  Old Raw: [{old_raw}]")
    print(f"  New Extracted Price: {new_price}")

if __name__ == "__main__":
    snapshots_dir = os.path.join(project_root, "snapshots")
    if os.path.exists(snapshots_dir):
        # Look for cropped images
        files = [f for f in os.listdir(snapshots_dir) if "_cropped" in f]
        # Sort by date (if possible)
        files.sort()
        
        # Test a few interesting ones (including potential misreads)
        for f in files[-10:]: 
            test_ocr_comparison(os.path.join(snapshots_dir, f))
    else:
        print("Snapshots directory not found.")
