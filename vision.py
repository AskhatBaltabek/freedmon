import cv2
import pytesseract
import re
import os
from datetime import datetime

import json

def load_crop_config():
    config_file = "crop_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    # Default fallback
    return {"crop_x": 0, "crop_y": 0, "crop_w": 10, "crop_h": 10}

def capture_snapshot(folder="snapshots", camera_index=0):
    config = load_crop_config()
    crop_x, crop_y = config.get("crop_x", 0), config.get("crop_y", 0)
    crop_w, crop_h = config.get("crop_w", 10), config.get("crop_h", 10)

    if not os.path.exists(folder):
        os.makedirs(folder)
    
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
    # Test with dummy image or just check camera
    print("Testing camera snapshot...")
    path = capture_snapshot()
    if path:
        print(f"Captured: {path}")
        price = extract_freedom_price(path)
        print(f"Extracted Price: {price}")
    else:
        print("Camera capture failed (expected in current environment).")
