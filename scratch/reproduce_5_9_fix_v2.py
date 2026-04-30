import cv2
import pytesseract
import os
import re
import numpy as np

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_advanced(img, scale=5, preprocess='none', psm=7):
    # Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Resize
    scaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    if preprocess == 'sharpen':
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        scaled = cv2.filter2D(scaled, -1, kernel)
    elif preprocess == 'blur_thresh':
        scaled = cv2.GaussianBlur(scaled, (5,5), 0)
        _, scaled = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif preprocess == 'morph':
        _, scaled = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((3,3), np.uint8)
        scaled = cv2.morphologyEx(scaled, cv2.MORPH_OPEN, kernel)
    else:
        _, scaled = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Config
    config = f'--psm {psm} -c tessedit_char_whitelist=0123456789.,=FT'
    
    try:
        text = pytesseract.image_to_string(scaled, config=config).strip()
        return text
    except Exception as e:
        return f"ERR: {e}"

def reproduce_v2():
    img_path = r"snapshots\adb_snapshot_20260415_222051_cropped.png"
    img = cv2.imread(img_path)
    
    print(f"Testing reproduction v2 on: {img_path}")
    
    methods = [
        (5, 'none', 7),
        (5, 'sharpen', 7),
        (5, 'blur_thresh', 7),
        (5, 'morph', 7),
        (5, 'none', 8), # PSM 8 (Single word)
        (7, 'none', 7), # Even larger scale
    ]
    
    for m in methods:
        scale, prep, psm = m
        res = ocr_advanced(img, scale, prep, psm)
        print(f"Scale={scale}, Prep={prep}, PSM={psm} => [{res}]")

if __name__ == "__main__":
    reproduce_v2()
