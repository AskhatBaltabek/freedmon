import cv2
import pytesseract
import os

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def test_psm8():
    snapshots_dir = r"snapshots"
    files = [f for f in os.listdir(snapshots_dir) if "_cropped" in f]
    files.sort()
    
    print("Testing PSM 8 on recent snapshots:")
    for f in files[-5:]:
        img_path = os.path.join(snapshots_dir, f)
        img = cv2.imread(img_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        scaled = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Test PSM 7 vs PSM 8
        txt7 = pytesseract.image_to_string(thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789.,=FT').strip()
        txt8 = pytesseract.image_to_string(thresh, config='--psm 8 -c tessedit_char_whitelist=0123456789.,=FT').strip()
        print(f"File: {f} | PSM7: [{txt7}] | PSM8: [{txt8}]")

if __name__ == "__main__":
    test_psm8()
