import time
import subprocess
from datetime import datetime

# --- CONFIGURATION ---
TARGET_TIME = "20:00:00"  # Set your target time (24-hour format HH:MM:SS)
# ---------------------

print(f"Waiting for target time: {TARGET_TIME}...")

while True:
    now = datetime.now().strftime("%H:%M:%S")
    if now == TARGET_TIME:
        # ydotool click 4000 means "Left Click" (1 = down, 2 = up, 4000 = both)
        subprocess.run(["ydotool", "click", "4000"], check=True)
        print("Successfully clicked through Wayland security!")
        break
    time.sleep(0.001)  # High-precision loop
