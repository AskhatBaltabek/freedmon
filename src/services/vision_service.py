import cv2
import pytesseract
import re
import os
import time
import subprocess
import logging
from datetime import datetime
from typing import Optional, Union

from src.core.config import Config

logger = logging.getLogger(__name__)

class VisionService:
    """Service handling ADB screenshots and OCR processing."""
    
    ADB_PATHS = [
        r"c:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        r"c:\Users\User\Downloads\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\adb.exe",
        "adb"
    ]
    
    def __init__(self):
        self.adb_path = self._find_adb()
        self._ensure_tesseract_path()
        # WiFi: connect to device if IP is configured
        self.device_target = self._connect_wifi()

    def _find_adb(self) -> Optional[str]:
        for path in self.ADB_PATHS:
            try:
                subprocess.run([path, "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return path
            except FileNotFoundError:
                continue
        logger.error("ADB executable not found. Please check paths.")
        return None

    def _connect_wifi(self) -> Optional[str]:
        """Connects to Android device over WiFi via ADB. Returns 'IP:PORT' target or None for USB."""
        ip = Config.DEVICE_IP.strip()
        port = Config.DEVICE_PORT.strip()
        if not ip or not self.adb_path:
            logger.info("ADB WiFi: no DEVICE_IP set, using USB connection.")
            return None
        target = f"{ip}:{port}"
        logger.info(f"ADB WiFi: connecting to {target}...")
        try:
            result = subprocess.run(
                [self.adb_path, "connect", target],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout.strip()
            logger.info(f"ADB connect result: {output}")
            if "connected" in output.lower():
                logger.info(f"ADB WiFi: successfully connected to {target}")
                return target
            else:
                logger.warning(f"ADB WiFi: connection failed — {output}. Falling back to USB.")
                return None
        except Exception as e:
            logger.error(f"ADB WiFi connect error: {e}. Falling back to USB.")
            return None

    def _adb_cmd(self, *args) -> list:
        """Builds an ADB command list, inserting -s <target> when using WiFi."""
        if self.device_target:
            return [self.adb_path, "-s", self.device_target, *args]
        return [self.adb_path, *args]

    def _ensure_tesseract_path(self):
        # pytesseract defaults 'tesseract_cmd' to 'tesseract', so we must unconditionally set the absolute path.
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    def capture_adb_screenshot(self, folder: str = Config.SNAPSHOTS_DIR, refresh: bool = True) -> Optional[str]:
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        if not self.adb_path:
            return None

        if refresh:
            mode = f"WiFi ({self.device_target})" if self.device_target else "USB"
            logger.info(f"Refreshing screen via ADB swipe down [{mode}]...")
            try:
                subprocess.run(
                    self._adb_cmd("shell", "input", "swipe", "500", "500", "500", "2000", "300"),
                    check=False
                )
                time.sleep(4)
            except Exception as e:
                logger.warning(f"Failed to execute swipe command: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = os.path.join(folder, f"adb_snapshot_{timestamp}.png")
        
        try:
            result = subprocess.run(self._adb_cmd("exec-out", "screencap", "-p"), capture_output=True)
            if result.returncode == 0:
                with open(image_path, "wb") as f:
                    f.write(result.stdout)
                return image_path
            else:
                logger.error(f"ADB command failed with return code {result.returncode}")
                return None
        except Exception as e:
            logger.error(f"Error during ADB screenshot: {e}")
            return None

    def capture_snapshot(self, folder: str = Config.SNAPSHOTS_DIR, refresh: bool = True) -> Optional[str]:
        """Wrapper for capture methods. Currently exclusively uses ADB."""
        return self.capture_adb_screenshot(folder=folder, refresh=refresh)

    def preprocess_image(self, img):
        """Applies Advanced OCR preprocessing."""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
            
        resized = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        denoised = cv2.bilateralFilter(resized, 9, 75, 75)
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh

    def extract_freedom_price(self, image_path_or_img: Union[str, any]) -> Optional[float]:
        """Extracts numerical price taking robust measures against false readings."""
        if isinstance(image_path_or_img, str):
            if not os.path.exists(image_path_or_img):
                logger.error(f"Path does not exist: {image_path_or_img}")
                return None
            img = cv2.imread(image_path_or_img)
        else:
            img = image_path_or_img

        if img is None or img.size == 0:
            return None
        
        processed = self.preprocess_image(img)
        custom_config = r'--psm 8 -c tessedit_char_whitelist=0123456789.,=FT'

        try:
            text = pytesseract.image_to_string(processed, config=custom_config).strip()
            logger.debug(f"OCR Optimized Text: {text}")
        except Exception as e:
            logger.error(f"OCR Error: {e}")
            return None
        
        # Match standard prices with decimals
        matches = re.findall(r"(\d+[,.]\d+)", text)
        price_str = None
        
        if matches:
            price_str = matches[0].replace(",", ".")
            if price_str.startswith("77.") and len(price_str) > 5:
                 m = re.search(r"(\d[,.]\d+)", price_str)
                 if m:
                     price_str = m.group(1)
        else:
            # Fallback for eroded decimals
            match = re.search(r"(\d+)", text)
            if match:
                digits = match.group(1)
                if len(digits) >= 5:
                    price_str = digits[:-4] + "." + digits[-4:]
                else:
                    price_str = digits

        if price_str:
            try:
                val = float(price_str)
                if val > 100.0 or val < 0.1:
                    logger.warning(f"Extracted value {val} out of bounds. Ignoring.")
                    return None
                return val
            except ValueError:
                return None
        
        return None
