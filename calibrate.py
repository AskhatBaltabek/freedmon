import cv2
import json
import os
import time

CONFIG_FILE = "crop_config.json"

def main():
    print("Welcome to Camera Calibration Tool")
    print("Starting camera... Please wait.")
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Camera not found. Falling back to a dummy test frame for calibration...")
        import numpy as np
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 255
        cv2.putText(frame, "Freedom Finance App", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.putText(frame, "1 F = 472.58 T", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
    else:
        # Read a few frames to let the camera auto-expose
        for _ in range(5):
            ret, frame = cap.read()
            time.sleep(0.1)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            print("Failed to grab frame from camera.")
            return

    print("Instruction:")
    print("1. A window will open with the camera frame.")
    print("2. Use your mouse to draw a rectangle over the target area (e.g., the price).")
    print("3. Press ENTER or SPACE to confirm the selection.")
    print("4. Press 'c' to redraw the selection.")
    
    roi = cv2.selectROI("Calibration - Select Crop Area", frame, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()
    
    x, y, w, h = roi
    
    if w == 0 or h == 0:
        print("No area selected. Calibration cancelled.")
        return
        
    print(f"Selected area: x={x}, y={y}, width={w}, height={h}")
    
    cropped = frame[y:y+h, x:x+w]
    
    cv2.imshow("Cropped Result - Press 'y' to save, 'n' to cancel", cropped)
    print("Check the cropped image window. Press 'y' to save or 'n' to cancel/discard.")
    
    key = cv2.waitKey(0) & 0xFF
    cv2.destroyAllWindows()
    
    if key == ord('y'):
        config = {
            "crop_x": int(x),
            "crop_y": int(y),
            "crop_w": int(w),
            "crop_h": int(h)
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        print(f"Calibration saved to {CONFIG_FILE}. The monitoring app will now use these coordinates.")
    else:
        print("Calibration discarded.")

if __name__ == "__main__":
    main()
