import sys

print("==================================================")
print("           NFC TAG ID CAPTURE UTILITY             ")
print("==================================================")
print("Instructions:")
print("1. Click your mouse inside this terminal window so it's active.")
print("2. Scan a physical tag/fob.")
print("3. Note down the exact ID printed.")
print("4. Press Ctrl+C when you are completely finished.")
print("--------------------------------------------------\n")

try: 
    while True:
        raw_id = input("Place tag on reader -> Scanned ID: ").strip()
        if raw_id:
            print(f"Captured Tag ID: {raw_id}\n")
except KeyboardInterrupt:
    print("\nTag capture complete. Exiting utility.")
    sys.exit()