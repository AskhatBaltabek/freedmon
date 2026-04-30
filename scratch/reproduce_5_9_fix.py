import cv2
import pytesseract
import os
import re

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_with_settings(img, scale=3, thresh_type='otsu', invert=False, oem=3):
    # Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if invert:
        gray = cv2.bitwise_not(gray)
        
    # Resize
    scaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Denoise
    denoised = cv2.bilateralFilter(scaled, 9, 75, 75)
    
    # Threshold
    if thresh_type == 'otsu':
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif thresh_type == 'adaptive':
        thresh = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    else:
        thresh = denoised

    # Config
    config = f'--psm 7 --oem {oem} -c tessedit_char_whitelist=0123456789.,=FT'
    
    try:
        text = pytesseract.image_to_string(thresh, config=config).strip()
        return text
    except Exception as e:
        return f"ERR: {e}"

def reproduce():
    img_path = r"snapshots\adb_snapshot_20260415_222051_cropped.png"
    if not os.path.exists(img_path):
        print("Image not found.")
        return

    img = cv2.imread(img_path)
    
    print(f"Testing reproduction on: {img_path}")
    
    scenarios = [
        # (scale, thresh, invert, oem)
        (3, 'otsu', False, 3), # current fix
        (5, 'otsu', False, 3), # 5x scale
        (5, 'adaptive', False, 3), # adaptive
        (5, 'otsu', True, 3), # inverted
        (5, 'otsu', False, 1), # LSTM engine
        (2, 'otsu', False, 3), # smaller scale?
    ]
    
    for s in scenarios:
        scale, th, inv, oem = s
        res = ocr_with_settings(img, scale, th, inv, oem)
        print(f"Scale={scale}, Thresh={th}, Invert={inv}, OEM={oem} => [{res}]")

if __name__ == "__main__":
    reproduce()
