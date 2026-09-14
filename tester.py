from datetime import datetime
from colorama import init, Fore, Style
from evdev import InputDevice, ecodes
import requests
import sqlite3
import time
import threading
import tkinter as tk
from tkinter import messagebox

# --- Credentials ---
NOTION_TOKEN = "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"
DATABASE_ID = "372c2c61e2bb80709de3d2e0349661c3"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

init(autoreset=True)

# --- NFC Hardware Path & Key Mapping ---
NFC_DEVICE_PATH = '/dev/input/by-id/usb-IC_Reader_IC_Reader_08FF20171101-event-kbd'

KEY_MAP = {
    'KEY_0': '0', 'KEY_1': '1', 'KEY_2': '2', 'KEY_3': '3', 'KEY_4': '4',
    'KEY_5': '5', 'KEY_6': '6', 'KEY_7': '7', 'KEY_8': '8', 'KEY_9': '9',
    'KEY_A': 'A', 'KEY_B': 'B', 'KEY_C': 'C', 'KEY_D': 'D', 'KEY_E': 'E', 'KEY_F': 'F'
}

# --- Database Initialization ---
con = sqlite3.connect("inventory.db", check_same_thread=False)
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS inventory(rfid TEXT PRIMARY KEY, item_id TEXT, item_name TEXT, type TEXT, status TEXT, destination TEXT, access_level INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS user(id TEXT PRIMARY KEY, name TEXT, access_level INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS logs(timestamp TEXT, item_name TEXT, user_name TEXT, action TEXT)")
con.commit()

# --- Tkinter Kiosk UI Class ---
class KioskApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NFC Inventory Kiosk")
        self.root.geometry("1024x600")
        # self.root.attributes('-fullscreen', True) # Uncomment for full kiosk mode
        self.root.configure(bg="#1e1e2e")

        # Runtime Data Context
        self.active_item = None
        self.active_user = None
        self.selection_ready = threading.Event()
        self.chosen_destination = None

        # Main Interface Viewport Frame
        self.view_frame = tk.Frame(self.root, bg="#1e1e2e")
        self.view_frame.pack(fill="both", expand=True)

        self.show_standby_screen()

        # Start background hardware monitoring thread
        self.hardware_thread = threading.Thread(target=run_backend_logic, args=(self,), daemon=True)
        self.hardware_thread.start()

    def clear_view(self):
        for widget in self.view_frame.winfo_children():
            widget.destroy()

    def show_standby_screen(self):
        self.clear_view()
        tk.Label(self.view_frame, text="⚙️ System Ready", font=("Helvetica", 32, "bold"), fg="#a6e3a1", bg="#1e1e2e").pack(pady=100)
        tk.Label(self.view_frame, text="Scan Item Tag on the Reader to Begin...", font=("Helvetica", 18), fg="#cdd6f4", bg="#1e1e2e").pack(pady=10)

    def show_error(self, msg):
        self.clear_view()
        tk.Label(self.view_frame, text=msg, font=("Helvetica", 32, "bold"), fg="#f38ba8", bg="#1e1e2e").pack(pady=100)
        self.root.after(3000, self.show_standby_screen)

    def show_destination_menu(self, mode):
        self.clear_view()

        title_text = "📍 Where is this item going?" if mode == 'BORROWED' else "📥 Where are you returning this item to?"
        tk.Label(self.view_frame, text=title_text, font=("Helvetica", 24, "bold"), fg="#89b4fa", bg="#1e1e2e").pack(pady=30)

        grid_frame = tk.Frame(self.view_frame, bg="#1e1e2e")
        grid_frame.pack(expand=True)

        return_destinations = ['Programming', 'Electronics', 'Mechanism', 'Inventory']
        borrow_destinations = ['KDSE', 'Used in Robot', 'Used by member']

        destinations = borrow_destinations if mode == 'BORROWED' else return_destinations

        for i, dest in enumerate(destinations):
            row, col = i // 4, i % 4
            btn = tk.Button(
                grid_frame, text=dest, font=("Helvetica", 14, "bold"), bg="#313244", fg="#f5e0dc",
                activebackground="#f5e0dc", activeforeground="#1e1e2e", relief="flat", width=14, height=3,
                command=lambda d=dest: self.submit_destination(d)
            )
            btn.grid(row=row, column=col, padx=15, pady=15)

    def submit_destination(self, dest):
        self.chosen_destination = dest
        self.selection_ready.set()

    def flash_success(self, msg):
        messagebox.showinfo("Success", msg)
        self.show_standby_screen()

# --- Cloud Sync Engine ---
def sync_to_notion(item_name, item_type, destination, user_name, action, timestamp):
    url = "https://api.notion.com/v1/pages"
    iso_timestamp = timestamp.replace(" ", "T")

    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Item Name": {"title": [{"text": {"content": item_name}}]},
            "web": {"rich_text": [{"text": {"content": str(item_type or 'N/A')}}]},
            "Status": {"rich_text": [{"text": {"content": str(destination or 'N/A')}}]},
            "Action": {"rich_text": [{"text": {"content": action}}]},
            "TimeStamp": {"date": {"start": iso_timestamp}},
            "User Name": {"rich_text": [{"text": {"content": user_name}}]}
        }
    }
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"{Fore.GREEN}Successfully synced to Notion{Style.RESET_ALL}")
        else: 
            print(f"{Fore.YELLOW}Cloud sync failed. Notion Error: {response.text}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error syncing to Notion: {e}{Style.RESET_ALL}")

# --- Non-blocking evdev NFC Scanner Helper ---
def scan_nfc_tag(dev, timeout=15):
    """Intermits background NFC scans directly from evdev hardware interface."""
    tag_buffer = ""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            for ev in dev.read():
                if ev.type == ecodes.EV_KEY and ev.value == 1:
                    key = ecodes.KEY[ev.code]
                    if key == 'KEY_ENTER':
                        return tag_buffer.strip()
                    elif key in KEY_MAP:
                        tag_buffer += KEY_MAP[key]
        except BlockingIOError:
            pass
        time.sleep(0.02)
    return None

def run_backend_logic(app):
    # Connect directly to hardware device
    try:
        reader = InputDevice(NFC_DEVICE_PATH)
        reader.grab()  # Captures scan events exclusively without typing into active terminal windows
        print(f"{Fore.GREEN}Hardware Reader Active: {reader.name}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error opening hardware NFC reader: {e}{Style.RESET_ALL}")
        app.root.after(0, lambda: app.show_error("NFC Reader Hardware Error"))
        return

    while True:        
        print(Fore.BLUE + "\n--- NFC Inventory Management System ---")
        print("Waiting for Item Scan...")
        
        # 1. Capture Item Scan
        item_id = scan_nfc_tag(reader, timeout=60)
        if not item_id:
            continue
            
        item = cur.execute("SELECT * FROM inventory WHERE rfid=?", (item_id,)).fetchone()
        if not item:
            app.root.after(0, lambda: app.show_error("No item found with this tag"))
            print(f"{Fore.RED}No item found with tag: {item_id}{Style.RESET_ALL}")
            time.sleep(2)
            continue
            
        print(f"Found Item: {item['item_name']} [Status: {item['status']}]")
        print(Fore.CYAN + "Waiting for User Badge Scan...")

        # 2. Capture User Scan
        user_id = scan_nfc_tag(reader, timeout=15)
        if not user_id:
            app.root.after(0, app.show_standby_screen)
            print(f"{Fore.RED}User scan timed out.{Style.RESET_ALL}")
            continue
            
        user = cur.execute("SELECT * FROM user WHERE id=?", (user_id,)).fetchone()
        if not user:
            app.root.after(0, lambda: app.show_error("No authorized user found with this badge"))
            print(f"{Fore.RED}No authorized user found with badge: {user_id}{Style.RESET_ALL}")
            time.sleep(2)
            continue

        print(f"Found User: {user['name']} [Access Level: {user['access_level']}]")

        log = cur.execute("SELECT * FROM logs WHERE item_name=? ORDER BY timestamp DESC", (item['item_name'],)).fetchone()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. Process Transaction
        match item['status']:
            case 'In Storage':
                if user['access_level'] < item['access_level']:
                    app.root.after(0, lambda: app.show_error("You don't have access to borrow this item"))
                else:
                    app.selection_ready.clear()
                    app.root.after(0, lambda: app.show_destination_menu('BORROWED'))
                    
                    if not app.selection_ready.wait(timeout=30):
                        print(f"{Fore.RED}User interaction timeout.{Style.RESET_ALL}")
                        app.root.after(0, app.show_standby_screen)
                        continue
                        
                    dest = app.chosen_destination
                    cur.execute("UPDATE inventory SET status=?, destination=? WHERE rfid=?", (dest, dest, item['rfid']))
                    cur.execute("INSERT INTO logs VALUES(?, ?, ?, ?)", (current_time, item['item_name'], user['name'], 'BORROWED'))
                    con.commit()
                    
                    print(f"{Fore.GREEN}Item Borrowed Successfully to {dest}{Style.RESET_ALL}")
                    app.root.after(0, lambda d=dest: app.flash_success(f"Item checked out to {d}!"))
                    sync_to_notion(item['item_name'], item['type'], dest, user['name'], 'BORROWED', current_time)

            case _:
                if not log:
                    app.root.after(0, lambda: app.show_error("No active log entry found for this item"))
                    print(f"{Fore.RED}System Error: No active log entry found{Style.RESET_ALL}")
                elif log['user_name'] != user['name']:
                    app.root.after(0, lambda: app.show_error("Wrong User tried returning item"))
                else:
                    app.selection_ready.clear()
                    app.root.after(0, lambda: app.show_destination_menu('RETURNED'))
                    
                    if not app.selection_ready.wait(timeout=30):
                        print(f"{Fore.RED}User interaction timeout.{Style.RESET_ALL}")
                        app.root.after(0, app.show_standby_screen)
                        continue
                        
                    dest = app.chosen_destination
                    cur.execute("UPDATE inventory SET status='In Storage', destination=? WHERE rfid=?", (dest, item['rfid']))
                    cur.execute("INSERT INTO logs VALUES(?,?,?,?)", (current_time, item['item_name'], user['name'], 'RETURNED'))
                    con.commit()
                    
                    print(f"{Fore.GREEN}Item Returned Successfully to {dest}{Style.RESET_ALL}")
                    app.root.after(0, lambda d=dest: app.flash_success(f"Item returned safely to {d}!"))
                    sync_to_notion(item['item_name'], item['type'], dest, user['name'], 'RETURNED', current_time)
                    
        time.sleep(2)

def main():
    root = tk.Tk()
    app = KioskApp(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutting down system...")
    finally:
        con.close()

if __name__ == "__main__": 
    main()