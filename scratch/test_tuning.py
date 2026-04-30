import cv2
import pytesseract
import os

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_test(img, scale=3, thresh='otsu', psm=7, morph=False):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    if morph:
        # close small holes before thresholding
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        resized = cv2.morphologyEx(resized, cv2.MORPH_CLOSE, kernel)
        
    denoised = cv2.bilateralFilter(resized, 9, 75, 75)
    
    if thresh == 'otsu':
        _, t = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif thresh == 'adaptive':
        t = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
    if morph:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
        t = cv2.morphologyEx(t, cv2.MORPH_OPEN, kernel)
        
    config = f'--psm {psm} -c tessedit_char_whitelist=0123456789.,=FT'
    return pytesseract.image_to_string(t, config=config).strip()

if __name__ == "__main__":
    folder = "snapshots"
    test_files = [
        "adb_snapshot_20260415_222051.png",     # The one where 5 becomes 9
        "adb_snapshot_20260416_003621.png"     # The one where 6 becomes 8
    ]
    
    configs = [
        (3, 'otsu', 7, False),     # Original
        (5, 'adaptive', 8, False), # Current bad aggressive
        (4, 'otsu', 7, False),     # Middle ground scale, psm 7
        (3, 'otsu', 8, False),     # Original scale, but psm 8
        (4, 'otsu', 8, False),
        (3, 'adaptive', 7, False),
    ]
    
    for f in test_files:
        p = os.path.join(folder, f)
        if not os.path.exists(p):
            print(f"File missing: {f}")
            continue
        
        img = cv2.imread(p)
        c = img[1865:1935, 280:472]
        
        print(f"\n--- {f} ---")
        for scale, th, psm, morph in configs:
            res = ocr_test(c, scale, th, psm, morph)
            print(f"Scale={scale}, Thresh={th}, PSM={psm} => [{res}]")
