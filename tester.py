from datetime import datetime
from logging import root
from colorama import init, Fore, Style
import requests
import select
import sys
import sqlite3
import time
import threading
import tkinter as tk
from tkinter import messagebox

# --- Credentials ---
# NOTION_TOKEN = ""
# DATABASE_ID = ""

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

init(autoreset=True)

# --- Database Initialization ---
con = sqlite3.connect("inventory.db", check_same_thread=False)  # Allowed multi-thread usage for GUI
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
        # self.root.attributes('-fullscreen', True) # Uncomment for headless Pi deployment
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
        self.hardware_thread = threading.Thread(target=run_backend_logic, args=(self,),daemon=True)
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

        # Large finger-friendly choices
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
        self.selection_ready.set()  # Notify backend loop to resume execution

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
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"{Fore.GREEN}Successfully synced to Notion{Style.RESET_ALL}")
        else: 
            print(f"{Fore.YELLOW}Cloud sync failed. Notion Error: {response.text}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error syncing to Notion: {e}{Style.RESET_ALL}")

def timed_input(prompt, timeout=15):
    print(prompt, end='', flush=True)
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if ready:
        return sys.stdin.readline().strip()
    else:
        print(f"\n{Fore.RED}Timeout reached{Style.RESET_ALL}")
        return None

def run_backend_logic(app):
    while True:        
        print(Fore.BLUE + "\n--- NFC Inventory Management System ---")
        item_id = input("Scan Item Tag: ").strip()
        item = cur.execute("SELECT * FROM inventory WHERE rfid=?", (item_id,)).fetchone()

        if not item:
            app.show_error("No item found with this tag")
            print(f"{Fore.RED}No item found with this tag{Style.RESET_ALL}")
            continue
        print(f"Found Item: {item['item_name']} [Status: {item['status']}]")

        user_id = timed_input(Fore.CYAN + "Scan User Tag: ", timeout=15)
        if not user_id:
            continue
        user = cur.execute("SELECT * FROM user WHERE id=?", (user_id,)).fetchone()

        if not user:
            app.show_error("No authorized user found with this badge")
            print(f"{Fore.RED}No authorized user found with this badge{Style.RESET_ALL}")
            continue

        print(f"Found User: {user['name']} [Access Level: {user['access_level']}]")

        log = cur.execute("SELECT * FROM logs WHERE item_name=? ORDER BY timestamp DESC", (item['item_name'],)).fetchone()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        match item['status']:
            case 'In Storage':
                if (user['access_level'] < item['access_level']):
                    app.show_error("You don't have access to borrow this item")
                else:
                    # 🚀 INTERFACE TRIGGER: Ask user for destination via touch panel
                    app.selection_ready.clear()
                    app.root.after(0, lambda: app.show_destination_menu('BORROWED'))
                    
                    # Wait for UI touch event acknowledgment
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

            case _:  # Treated as a Return path if status is Checked Out / any active location
                if not log:
                    app.show_error("No active log entry found for this item")
                    print(f"{Fore.RED}System Error: No active log entry found{Style.RESET_ALL}")
                elif log['user_name'] != user['name']:
                    app.show_error("Wrong User tried returning item")
                else:
                    # 🚀 INTERFACE TRIGGER: Ask user for return target via touch panel
                    app.selection_ready.clear()
                    app.root.after(0, lambda: app.show_destination_menu('RETURNED'))
                    
                    if not app.selection_ready.wait(timeout=30):
                        app.show_error("User interaction timeout")
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