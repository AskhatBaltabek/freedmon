# Redirects for backward compatibility with older scripts in the root directory.
from src.services.vision_service import VisionService

_service = VisionService()

def capture_snapshot(folder="snapshots", camera_index=0, mode="adb", refresh=True):
    return _service.capture_snapshot(folder, refresh)

def extract_freedom_price(image_path_or_img):
    return _service.extract_freedom_price(image_path_or_img)
