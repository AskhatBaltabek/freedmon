import cv2
import pytesseract
import os

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_old(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    denoised = cv2.bilateralFilter(resized, 9, 75, 75)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    config = r'--psm 7 -c tessedit_char_whitelist=0123456789.,=FT'
    return pytesseract.image_to_string(thresh, config=config).strip()

def ocr_new(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    denoised = cv2.bilateralFilter(resized, 9, 75, 75)
    thresh = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    config = r'--psm 8 -c tessedit_char_whitelist=0123456789.,=FT'
    return pytesseract.image_to_string(thresh, config=config).strip()

if __name__ == "__main__":
    folder = "snapshots"
    # Find all cropped images or just main images and crop them
    
    # We don't have cropped images because the new logic uses vision_service.py which does not save cropped images
    # Let's read the main images and apply the crop manually
    import json
    with open('crop_config.json', 'r') as f:
        crop = json.load(f)
    cx, cy, cw, ch = crop['crop_x'], crop['crop_y'], crop['crop_w'], crop['crop_h']
    
    # Wait, the main.py previously used hardcoded crop:
    # cropped = img[1865:1935, 280:472]
    # Let's check which files exist
    files = [f for f in os.listdir(folder) if f.endswith(".png") and "cropped" not in f]
    files.sort()
    
    for f in files[-5:]:
        img_path = os.path.join(folder, f)
        img = cv2.imread(img_path)
        if img is not None:
            c = img[1865:1935, 280:472] # previous main.py crop
            if c.size > 0:
                print(f"--- {f} ---")
                print(f"Old: [{ocr_old(c)}]")
                print(f"New: [{ocr_new(c)}]")
