import cv2
import pytesseract
import os
import re

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def test_ocr(image_path):
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load image: {image_path}")
        return

    # 1. Original (Gray)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. Resized
    resized = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    
    # 3. Thresholding
    # Try different thresholding methods
    # Simple Thresholding
    _, thresh1 = cv2.threshold(resized, 150, 255, cv2.THRESH_BINARY)
    # Adaptive Thresholding
    thresh2 = cv2.adaptiveThreshold(resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    # Otsu's Thresholding
    _, thresh3 = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # OCR configs
    configs = [
        '--psm 7',  # Single line
        '--psm 7 -c tessedit_char_whitelist=0123456789.,=FT',
        '--psm 6',  # Uniform block
        '--psm 6 -c tessedit_char_whitelist=0123456789.,=FT'
    ]

    print(f"\n--- Testing IMAGE: {image_path} ---")
    
    methods = [
        ("Original Gray", gray),
        ("Resized Gray", resized),
        ("Simple Thresh", thresh1),
        ("Adaptive Thresh", thresh2),
        ("Otsu Thresh", thresh3)
    ]

    for m_name, m_img in methods:
        print(f"\nMethod: {m_name}")
        for config in configs:
            try:
                text = pytesseract.image_to_string(m_img, config=config).strip()
                print(f"  Config '{config}': [{text}]")
            except Exception as e:
                print(f"  Config '{config}': Error {e}")

if __name__ == "__main__":
    # Test on a few cropped images
    snapshots_dir = r"c:\Users\User\Desktop\work\freedmon\snapshots"
    if os.path.exists(snapshots_dir):
        files = [f for f in os.listdir(snapshots_dir) if "_cropped" in f]
        for f in files[-3:]: # Test last 3
            test_ocr(os.path.join(snapshots_dir, f))
    else:
        print("Snapshots directory not found.")
