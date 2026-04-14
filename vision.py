import cv2
import pytesseract
import re
import os
import time
import subprocess
from datetime import datetime

# Configuration
# Path to ADB. You can set this to "adb" if it's in your PATH.
ADB_PATHS = [
    r"c:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    r"c:\Users\User\Downloads\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\adb.exe",
    "adb"
]

def find_adb():
    for path in ADB_PATHS:
        try:
            subprocess.run([path, "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return path
        except FileNotFoundError:
            continue
    return None

def capture_adb_screenshot(folder="snapshots", refresh=True):
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    adb_path = find_adb()
    if not adb_path:
        print("Error: adb.exe not found. Please install ADB or set the correct path.")
        return None

    if refresh:
        print("Refreshing screen via ADB swipe down...")
        try:
            # Swipe from x=500, y=500 to x=500, y=2000 over 300ms
            subprocess.run([adb_path, "shell", "input", "swipe", "500", "500", "500", "2000", "300"], check=False)
            # Wait for the network request/animation to finish
            print("Waiting for refresh to complete...")
            time.sleep(4)
        except Exception as e:
            print(f"Failed to execute swipe command: {e}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = os.path.join(folder, f"adb_snapshot_{timestamp}.png")
    
    try:
        # Take screenshot and save it to the folder
        # We use 'shell screencap -p' to get PNG data and redirect to local file
        # In PowerShell/Command Prompt, redirection might need care if using subprocess
        # Better: capture output and write to file or use adb exec-out
        result = subprocess.run([adb_path, "exec-out", "screencap", "-p"], capture_output=True)
        if result.returncode == 0:
            with open(image_path, "wb") as f:
                f.write(result.stdout)
            return image_path
        else:
            print(f"Error: ADB command failed with return code {result.returncode}")
            return None
    except Exception as e:
        print(f"Error during ADB screenshot: {e}")
        return None

def capture_snapshot(folder="snapshots", camera_index=0, mode="adb", refresh=True):
    if mode == "adb":
        path = capture_adb_screenshot(folder, refresh=refresh)
        if path:
            return path
        print("Falling back to camera capture...")

    if not os.path.exists(folder):
        os.makedirs(folder)

    # If we are in a mock-only environment (like Docker on Windows without usbipd), 
    # skip the camera attempt to avoid noisy OpenCV warnings.
    if os.environ.get("USE_MOCK_CAMERA", "0") == "1":
        print("USE_MOCK_CAMERA=1 detected. Using mock image.")
        return create_dummy_image(folder)
    # If running natively on Windows, DirectShow acts faster and is more reliable.
    # If running inside Docker (Linux), just use the default backend.
    if os.name == 'nt':
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Error: Could not open camera {camera_index}. Creating dummy image for testing.")
        return create_dummy_image(folder, crop_x, crop_y, crop_w, crop_h)
    
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame. Creating dummy image for testing.")
        cap.release()
        return create_dummy_image(folder, crop_x, crop_y, crop_w, crop_h)
    
    # Apply crop based on coordinates
    if crop_w > 0 and crop_h > 0:
        frame = frame[crop_y:crop_y+crop_h, crop_x:crop_x+crop_w]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = os.path.join(folder, f"snapshot_{timestamp}.jpg")
    cv2.imwrite(image_path, frame)
    
    cap.release()
    return image_path

def create_dummy_image(folder="snapshots", crop_x=0, crop_y=0, crop_w=10, crop_h=10):
    import numpy as np
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # Create a white image
    img = np.ones((480, 640, 3), dtype=np.uint8) * 255
    # Add some text that looks like the Freedom app
    cv2.putText(img, "Freedom Finance App", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(img, "1 F = 472.58 T", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
    
    # Apply crop based on coordinates
    if crop_w > 0 and crop_h > 0:
        img = img[crop_y:crop_y+crop_h, crop_x:crop_x+crop_w]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = os.path.join(folder, f"mock_{timestamp}.jpg")
    cv2.imwrite(image_path, img)
    print(f"Created mock image: {image_path}")
    return image_path

def extract_freedom_price(image_path):
    if not image_path or not os.path.exists(image_path):
        return None
    
    # Load image
    img = cv2.imread(image_path)
    # Preprocessing for OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Optional: thresholding, resizing, etc.
    
    # OCR
    # Format: "1 F = X.XXXX T"
    try:
        text = pytesseract.image_to_string(gray)
        print(f"OCR Raw Text: {text}")
    except Exception as e:
        print(f"OCR Error: {e}")
        return None
    
    # Regex to find the pattern: 1 F = [price] T
    # Accommodating potential OCR errors (spaces, dots vs commas)
    match = re.search(r"1\s*F\s*=\s*(\d+[,.]\d+)", text, re.IGNORECASE)
    if match:
        price_str = match.group(1).replace(",", ".")
        try:
            return float(price_str)
        except ValueError:
            return None
    
    return None

if __name__ == "__main__":
    # Test with ADB screenshot
    print("Testing ADB snapshot...")
    path = capture_snapshot(mode="adb")
    if path:
        print(f"Captured: {path}")
        # If tesseract is not in path, you might need:
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        price = extract_freedom_price(path)
        if price:
            print(f"Extracted Price: {price}")
        else:
            print("Could not extract price from image.")
    else:
        print("Capture failed.")
