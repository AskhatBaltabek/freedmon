import os
import glob
from datetime import datetime, timedelta
from typing import Optional
from src.core.config import Config

class BusinessLogger:
    """Handles business-specific daily execution logs and retention."""
    
    LOGS_DIR = os.path.join(Config.ROOT_DIR, "logs")

    @classmethod
    def _ensure_dir(cls):
        if not os.path.exists(cls.LOGS_DIR):
            os.makedirs(cls.LOGS_DIR)

    @classmethod
    def log_cycle(cls, snapshot_price: Optional[float],
                  usd_kzt: Optional[float], 
                  live: Optional[float], 
                  pre: Optional[float], 
                  post: Optional[float], 
                  calculated_rate: Optional[float], 
                  difference_pct: Optional[float]):
        """Writes cycle execution state into a daily file."""
        cls._ensure_dir()
        
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        filename = os.path.join(cls.LOGS_DIR, f"execution_{date_str}.log")
        
        # Formatting values safely
        snap_v = f"{snapshot_price:.4f}" if snapshot_price is not None else "N/A"
        usd_v = f"{usd_kzt:.2f}" if usd_kzt is not None else "N/A"
        live_v = f"{live:.2f}" if live is not None else "N/A"
        pre_v = f"{pre:.2f}" if pre is not None else "N/A"
        post_v = f"{post:.2f}" if post is not None else "N/A"
        calc_v = f"{calculated_rate:.4f}" if calculated_rate is not None else "N/A"
        diff_v = f"{difference_pct:.2f}%" if difference_pct is not None else "N/A"
        
        log_entry = (
            f"[{time_str}] "
            f"OCR Snapshot: {snap_v} | "
            f"USD/KZT: {usd_v} | "
            f"FRHC: (Live:{live_v}, Pre:{pre_v}, Post:{post_v}) | "
            f"Calculated: {calc_v} | "
            f"Diff: {diff_v}\n"
        )
        
        try:
            with open(filename, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            # Fallback print if file writing fails
            print(f"Error writing to business log: {e}")

    @classmethod
    def cleanup_old_logs(cls):
        """Cleans up logs older than 7 days (weekly cleanup)."""
        cls._ensure_dir()
        retention_days = 7
        now = datetime.now()
        deleted = 0
        
        for filepath in glob.glob(os.path.join(cls.LOGS_DIR, "execution_*.log")):
            try:
                # Extract date from filename: execution_YYYY-MM-DD.log
                basename = os.path.basename(filepath)
                date_part = basename.replace("execution_", "").replace(".log", "")
                log_date = datetime.strptime(date_part, "%Y-%m-%d")
                
                # If older than 7 days, delete
                if (now - log_date).days >= retention_days:
                    os.remove(filepath)
                    deleted += 1
            except Exception as e:
                print(f"Error checking/deleting file {filepath}: {e}")
                
        return deleted
