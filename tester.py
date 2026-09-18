from datetime import datetime
from colorama import init, Fore, Style
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

# --- Database Initialization ---
con = sqlite3.connect("inventory.db", check_same_thread=False)
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS inventory(rfid TEXT PRIMARY KEY, item_id TEXT, type TEXT, status TEXT, current_location TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS user(id TEXT PRIMARY KEY, name TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS logs(timestamp TEXT, item_id TEXT, user_name TEXT, action TEXT)")
con.commit()

# --- Tkinter Kiosk UI Class ---
class KioskApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NFC Inventory Kiosk")
        self.root.geometry("1024x600")
        self.root.configure(bg="#1e1e2e")

        # Runtime Data Context
        self.active_item = None
        self.active_user = None
        self.selection_ready = threading.Event()
        self.chosen_destination = None

        # Key Capture Buffer
        self.scan_buffer = ""
        self.scan_ready_event = threading.Event()
        self.latest_scanned_tag = ""

        # Bind all keyboard events directly to Tkinter window focus
        self.root.bind("<Key>", self.handle_keypress)

        # Main Interface Viewport Frame
        self.view_frame = tk.Frame(self.root, bg="#1e1e2e")
        self.view_frame.pack(fill="both", expand=True)

        self.show_standby_screen()

        # Start background hardware monitoring thread
        self.hardware_thread = threading.Thread(target=run_backend_logic, args=(self,), daemon=True)
        self.hardware_thread.start()

    def handle_keypress(self, event):
        """Captures hardware USB keyboard scans when Tkinter window is focused."""
        if event.keysym == 'Return':
            if self.scan_buffer.strip():
                self.latest_scanned_tag = self.scan_buffer.strip()
                self.scan_buffer = ""
                self.scan_ready_event.set()
        elif len(event.char) == 1 and event.char.isprintable():
            self.scan_buffer += event.char

    def wait_for_scan(self, timeout=30):
        """Thread-safe wait for next tag scan from focused GUI window."""
        self.scan_ready_event.clear()
        if self.scan_ready_event.wait(timeout=timeout):
            return self.latest_scanned_tag
        return None

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

        title_text = "📍 Where is this item going?" if mode == 'Borrowing' else "📥 Where are you returning this item to?"
        tk.Label(self.view_frame, text=title_text, font=("Helvetica", 24, "bold"), fg="#89b4fa", bg="#1e1e2e").pack(pady=30)

        grid_frame = tk.Frame(self.view_frame, bg="#1e1e2e")
        grid_frame.pack(expand=True)

        return_destinations = ['Drawer', 'Safe']
        borrow_destinations = ['Robot', 'Testing']

        destinations = borrow_destinations if mode == 'Borrowing' else return_destinations

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
def sync_to_notion(item_name, item_type, status, taken_by, from_, to_, timestamp):
    url = "https://api.notion.com/v1/pages"
    iso_timestamp = timestamp.replace(" ", "T")

    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Item ID": {"title": [{"text": {"content": str(item_name)}}]},
            "Type": {"rich_text": [{"text": {"content": str(item_type or 'N/A')}}]},
            "Status": {"rich_text": [{"text": {"content": str(status or 'N/A')}}]},
            "Taken By": {"rich_text": [{"text": {"content": str(taken_by or 'N/A')}}]},
            "From": {"rich_text": [{"text": {"content": str(from_ or 'N/A')}}]},
            "To": {"rich_text": [{"text": {"content": str(to_ or 'N/A')}}]},
            "Date Taken": {"date": {"start": iso_timestamp}},
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

def run_backend_logic(app):
    while True:        
        print(Fore.BLUE + "\n--- NFC Inventory Management System ---")
        print("Waiting for Item Scan (Scan on focused Kiosk Window)...")
        
        # Capture Item Tag via Tkinter Event Listener
        item_id = app.wait_for_scan(timeout=60)
        if not item_id:
            continue

        item = cur.execute("SELECT * FROM inventory WHERE rfid=?", (item_id,)).fetchone()

        if not item:
            app.root.after(0, lambda: app.show_error("No item found with this tag"))
            print(f"{Fore.RED}No item found with tag: {item_id}{Style.RESET_ALL}")
            time.sleep(2)
            continue
        print(f"Found Item: {item['item_id']} [Status: {item['status']}]")

        print(Fore.CYAN + "Scan User Badge: ")
        user_id = app.wait_for_scan(timeout=15)
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

        print(f"Found User: {user['name']}")

        log = cur.execute("SELECT * FROM logs WHERE item_id =? ORDER BY timestamp DESC", (item['item_id'],)).fetchone()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        match item['status']:
            case 'Available':
                app.selection_ready.clear()
                app.root.after(0, lambda: app.show_destination_menu('Borrowing'))
                
                if not app.selection_ready.wait(timeout=30):
                    print(f"{Fore.RED}User interaction timeout.{Style.RESET_ALL}")
                    app.root.after(0, app.show_standby_screen)
                    continue
                
                dest = app.chosen_destination
                previous_dest = item['current_location'] or 'N/A'

                cur.execute("UPDATE inventory SET status=?, current_location=? WHERE rfid=?", ('Allocated', dest, item['rfid']))
                cur.execute("INSERT INTO logs VALUES(?, ?, ?, ?)", (current_time, item['item_id'], user['name'], 'Borrow'))
                con.commit()

                app.root.after(0, lambda d=dest: app.flash_success(f"Item checked out to {d}!"))
                
                # Correct non-blocking thread invocation with real variables:
                threading.Thread(
                    target=sync_to_notion, 
                    args=(item['item_id'], item['type'], 'Allocated', user['name'], previous_dest, dest, current_time), 
                    daemon=True
                ).start()

                print(f"{Fore.GREEN}Item Borrowed Successfully to {dest}{Style.RESET_ALL}")
                
            case 'Allocated':
                if not log:
                    app.root.after(0, lambda: app.show_error("No active log entry found for this item"))
                    print(f"{Fore.RED}System Error: No active log entry found{Style.RESET_ALL}")
                elif log['user_name'] != user['name']:
                    app.root.after(0, lambda: app.show_error("Wrong User tried returning item"))
                else:
                    app.selection_ready.clear()
                    app.root.after(0, lambda: app.show_destination_menu('Returning'))
                    
                    if not app.selection_ready.wait(timeout=30):
                        print(f"{Fore.RED}User interaction timeout.{Style.RESET_ALL}")
                        app.root.after(0, app.show_standby_screen)
                        continue
                        
                    dest = app.chosen_destination
                    previous_dest = item['current_location'] or 'N/A'

                    cur.execute("UPDATE inventory SET status='Available', current_location=? WHERE rfid=?", (dest, item['rfid']))
                    cur.execute("INSERT INTO logs VALUES(?,?,?,?)", (current_time, item['item_id'], user['name'], 'RETURNED'))
                    con.commit()

                    app.root.after(0, lambda d=dest: app.flash_success(f"Item returned safely to {d}!"))
                    
                    # Correct non-blocking thread invocation with real variables:
                    threading.Thread(
                        target=sync_to_notion, 
                        args=(item['item_id'], item['type'], 'Available', user['name'], previous_dest, dest, current_time), 
                        daemon=True
                    ).start()

                    print(f"{Fore.GREEN}Item Returned Successfully to {dest}{Style.RESET_ALL}")
        
        app.chosen_destination = None
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