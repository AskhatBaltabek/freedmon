import sys
import os

# Redirect to the new refactored Clean Architecture
print("Redirecting to the new refactored 'src/main.py' architecture...")

from src import main

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main.main())
    except KeyboardInterrupt:
        print("\nMonitoring app stopped.")
