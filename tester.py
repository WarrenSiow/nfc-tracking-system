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
DATABASE_ID = "2e55f987cbe68029a2c6e051873b4649"

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

cur.execute("CREATE TABLE IF NOT EXISTS inventory(rfid TEXT PRIMARY KEY, item_id TEXT, status TEXT, current_location TEXT)")
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
        self.active_user = None
        self.scanned_items = []
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
        """Thread-safe wait for next tag scan or GUI action button click."""
        self.scan_ready_event.clear()
        if self.scan_ready_event.wait(timeout=timeout):
            return self.latest_scanned_tag
        return None

    def clear_view(self):
        for widget in self.view_frame.winfo_children():
            widget.destroy()

    def show_standby_screen(self):
        self.clear_view()
        self.scanned_items = []
        tk.Label(self.view_frame, text="⚙️ System Ready", font=("Helvetica", 32, "bold"), fg="#a6e3a1", bg="#1e1e2e").pack(pady=100)
        tk.Label(self.view_frame, text="Scan User Tag on the Reader...", font=("Helvetica", 18), fg="#cdd6f4", bg="#1e1e2e").pack(pady=10)

    def item_scan_screen(self, user_name, items_list):
        self.clear_view()
        
        # User Header & Item Counter Display
        tk.Label(self.view_frame, text=f"👤 User: {user_name}", font=("Helvetica", 20, "bold"), fg="#89b4fa", bg="#1e1e2e").pack(pady=(20, 5))
        
        count = len(items_list)
        counter_fg = "#f38ba8" if count >= 20 else "#a6e3a1"
        tk.Label(self.view_frame, text=f"Items Scanned: {count} / 20", font=("Helvetica", 28, "bold"), fg=counter_fg, bg="#1e1e2e").pack(pady=10)
        
        tk.Label(self.view_frame, text="Scan next item tag or press Select Location below...", font=("Helvetica", 14), fg="#cdd6f4", bg="#1e1e2e").pack(pady=5)

        # Scanned Items List View (WIDER CONTAINER: padx reduced from 150 to 50)
        list_frame = tk.Frame(self.view_frame, bg="#313244", bd=2, relief="solid")
        list_frame.pack(pady=10, fill="both", expand=True, padx=50)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        items_box = tk.Listbox(
            list_frame, font=("Helvetica", 14), bg="#1e1e2e", fg="#f5e0dc",
            selectbackground="#45475a", yscrollcommand=scrollbar.set, bd=0
        )
        
        if not items_list:
            items_box.insert(tk.END, "  (No items scanned yet)")
        else:
            for idx, item_obj in enumerate(items_list, start=1):
                items_box.insert(tk.END, f"  {idx}. Item ID: {item_obj['item_id']}  [{item_obj['status']}]")

        items_box.pack(fill="both", expand=True)
        scrollbar.config(command=items_box.yview)

        # Bottom Button Container (Side-by-Side)
        button_container = tk.Frame(self.view_frame, bg="#1e1e2e")
        button_container.pack(pady=15)

        # Cancel Session Button (Red)
        cancel_btn = tk.Button(
            button_container, text="Cancel Session", font=("Helvetica", 14, "bold"),
            bg="#f38ba8", fg="#1e1e2e", activebackground="#e8a2af", relief="flat",
            width=18, height=2, command=lambda: self.submit_destination("CANCEL_SESSION")
        )
        cancel_btn.pack(side="left", padx=15)

        # Select Location Button (Grayed out if empty, Green when items exist)
        if items_list:
            done_btn = tk.Button(
                button_container, text="Select Location ➔", font=("Helvetica", 14, "bold"),
                bg="#a6e3a1", fg="#1e1e2e", activebackground="#cdd6f4", relief="flat",
                width=18, height=2, state="normal", command=lambda: self.submit_destination("FINISH_SCANNING")
            )
        else:
            done_btn = tk.Button(
                button_container, text="Select Location ➔", font=("Helvetica", 14, "bold"),
                bg="#45475a", fg="#a6adc8", relief="flat",
                width=18, height=2, state="disabled"
            )
        done_btn.pack(side="left", padx=15)

    def show_destination_menu(self, mode):
        self.clear_view()

        title_text = "📍 Where are these items going?" if mode == 'Borrowing' else "📥 Where are you returning these items to?"
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

        # Back / Return Button
        back_btn = tk.Button(
            self.view_frame, text="⬅ Back to Item Scan", font=("Helvetica", 12, "bold"),
            bg="#45475a", fg="#cdd6f4", activebackground="#585b70", activeforeground="#f5e0dc",
            relief="flat", width=22, height=2, command=lambda: self.submit_destination("GO_BACK")
        )
        back_btn.pack(pady=(10, 25))

    def submit_destination(self, dest):
        self.chosen_destination = dest
        self.selection_ready.set()
        self.scan_ready_event.set()  # Unblock wait_for_scan immediately on button click

    def flash_success(self, msg):
        messagebox.showinfo("Success", msg)
        self.show_standby_screen()

    def flash_failure(self, msg):
        messagebox.showerror("Error", msg)
        self.show_standby_screen()

# --- Cloud Sync Engine ---
def sync_to_notion(item_id, status, taken_by, from_, to_, timestamp):
    query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    query_payload = {
        "filter": {
            "property": "Item ID",
            "title": {
                "equals": str(item_id)
            }
        }
    }

    iso_timestamp = timestamp.replace(" ", "T")

    try:
        query_response = requests.post(query_url, json=query_payload, headers=HEADERS, timeout=5)

        if query_response.status_code == 200:
            results = query_response.json().get("results", [])

            if not results:
                print(f"{Fore.YELLOW}Item '{item_id}' not found in the database.{Style.RESET_ALL}")
                return

            page_id = results[0]["id"]
            update_url = f"https://api.notion.com/v1/pages/{page_id}"

            update_payload = {
                "properties": {
                    "Item ID": {"title": [{"text": {"content": str(item_id)}}]},
                    "Status": {"select": {"name": str(status or 'N/A')}},
                    "Taken By": {"rich_text": [{"text": {"content": str(taken_by or 'N/A')}}]},
                    "From": {"select": {"name": str(from_ or 'N/A')}},
                    "To": {"select": {"name": str(to_ or 'N/A')}},
                    "Date Taken": {"date": {"start": iso_timestamp}},
                }
            }

            patch_response = requests.patch(update_url, headers=HEADERS, json=update_payload, timeout=5)

            if patch_response.status_code == 200:
                print(f"{Fore.GREEN}Successfully updated Notion for {item_id}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to update Notion. Error: {patch_response.text}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to query Notion. Error: {query_response.text}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error syncing to Notion: {e}{Style.RESET_ALL}")

def run_backend_logic(app):
    while True:        
        print(Fore.BLUE + "\n--- NFC Inventory Management System ---")
        print("Waiting for User Scan\n(Scan on focused Kiosk Window)...")

        user_id = app.wait_for_scan(timeout=60)
        if not user_id:
            app.root.after(0, app.show_standby_screen)
            print(f"{Fore.RED}User scan timed out.{Style.RESET_ALL}")
            continue

        user = cur.execute("SELECT * FROM user WHERE id=?", (user_id,)).fetchone()

        if not user:
            app.root.after(0, lambda: app.flash_failure("No authorized user found"))
            print(f"{Fore.RED}No authorized user found with badge: {user_id}{Style.RESET_ALL}")
            time.sleep(2)
            continue

        print(f"Found User: {user['name']}")
        
        # Initialize Scanning Session
        scanned_items = []

        while True:
            app.selection_ready.clear()
            app.chosen_destination = None
            app.root.after(0, lambda: app.item_scan_screen(user['name'], scanned_items))

            # --- Item Scanning Loop (Limit 20 Items) ---
            while len(scanned_items) < 20:
                scanned_tag = app.wait_for_scan(timeout=45)

                # Check GUI button actions
                if app.selection_ready.is_set():
                    if app.chosen_destination == "FINISH_SCANNING":
                        break
                    elif app.chosen_destination == "CANCEL_SESSION":
                        scanned_items = []
                        break

                if not scanned_tag:
                    if not scanned_items:
                        print(f"{Fore.RED}Item scanning timed out.{Style.RESET_ALL}")
                    break

                item = cur.execute("SELECT * FROM inventory WHERE rfid=?", (scanned_tag,)).fetchone()

                if not item:
                    print(f"{Fore.RED}No item found with tag: {scanned_tag}{Style.RESET_ALL}")
                    continue

                # Check for Duplicate Scans in Current Session
                if any(i['rfid'] == item['rfid'] for i in scanned_items):
                    print(f"{Fore.YELLOW}Item {item['item_id']} already scanned in this session.{Style.RESET_ALL}")
                    continue

                # Ensure all scanned items in a batch have matching operational status
                if scanned_items and item['status'] != scanned_items[0]['status']:
                    print(f"{Fore.RED}Cannot mix Available and Allocated items in one scan session!{Style.RESET_ALL}")
                    continue

                # Validate Allocated Items (User Authorization Check)
                if item['status'] == 'Allocated':
                    log = cur.execute("SELECT * FROM logs WHERE item_id=? ORDER BY timestamp DESC", (item['item_id'],)).fetchone()
                    if not log or log['user_name'] != user['name']:
                        app.root.after(0, lambda: app.flash_failure(f"Wrong user tried returning item: {item['item_id']}"))
                        print(f"{Fore.RED}Unauthorized return attempt for item {item['item_id']}{Style.RESET_ALL}")
                        continue

                # Add Item to Session List
                scanned_items.append(dict(item))
                print(f"Scanned Item ({len(scanned_items)}/20): {item['item_id']} [{item['status']}]")

                # Refresh GUI List and Counter
                app.root.after(0, lambda: app.item_scan_screen(user['name'], scanned_items))

                # Stop scanning automatically if limit reached
                if len(scanned_items) == 20:
                    print(f"{Fore.YELLOW}Reached maximum limit of 20 items.{Style.RESET_ALL}")
                    break

            if not scanned_items:
                app.root.after(0, app.show_standby_screen)
                break

            # --- Destination Selection Phase ---
            session_mode = 'Borrowing' if scanned_items[0]['status'] == 'Available' else 'Returning'
            app.selection_ready.clear()
            app.chosen_destination = None
            app.root.after(0, lambda: app.show_destination_menu(session_mode))

            if not app.selection_ready.wait(timeout=30) or not app.chosen_destination:
                print(f"{Fore.RED}Destination selection timed out.{Style.RESET_ALL}")
                app.root.after(0, app.show_standby_screen)
                break

            # If user clicks "Back to Item Scan", loop back to item_scan_screen
            if app.chosen_destination == "GO_BACK":
                continue

            dest = app.chosen_destination
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # --- Process Database Updates and Async Notion Sync ---
            for item in scanned_items:
                previous_dest = item['current_location'] or 'N/A'

                if session_mode == 'Borrowing':
                    cur.execute("UPDATE inventory SET status=?, current_location=? WHERE rfid=?", ('Allocated', dest, item['rfid']))
                    cur.execute("INSERT INTO logs VALUES(?, ?, ?, ?)", (current_time, item['item_id'], user['name'], 'Borrow'))
                    con.commit()

                    threading.Thread(
                        target=sync_to_notion, 
                        args=(item['item_id'], 'Allocated', user['name'], previous_dest, dest, current_time), 
                        daemon=True
                    ).start()
                else:
                    cur.execute("UPDATE inventory SET status='Available', current_location=? WHERE rfid=?", (dest, item['rfid']))
                    cur.execute("INSERT INTO logs VALUES(?, ?, ?, ?)", (current_time, item['item_id'], user['name'], 'RETURNED'))
                    con.commit()

                    threading.Thread(
                        target=sync_to_notion, 
                        args=(item['item_id'], 'Available', user['name'], previous_dest, dest, current_time), 
                        daemon=True
                    ).start()

            action_msg = "borrowed to" if session_mode == 'Borrowing' else "returned to"
            app.root.after(0, lambda d=dest, c=len(scanned_items): app.flash_success(f"Successfully {action_msg} {d} ({c} items)!"))
            print(f"{Fore.GREEN}Processed {len(scanned_items)} items successfully to {dest}.{Style.RESET_ALL}")
            break

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