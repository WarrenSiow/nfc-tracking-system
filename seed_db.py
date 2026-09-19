# status = ["Available", "Allocated", "Repairing", "Lending"]
# return_destination = ["Safe", "Drawer"]
# borrow_destination = ["Robot", "Testing"]

import sqlite3

def seed():
    con = sqlite3.connect("inventory.db")
    cur = con.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS inventory(rfid TEXT PRIMARY KEY, item_id TEXT, type TEXT, status TEXT, current_location TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS user(id TEXT PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS logs(timestamp TEXT, item_id TEXT, user_name TEXT, action TEXT)")
    
    cur.execute("DELETE FROM inventory")
    cur.execute("DELETE FROM user")
    cur.execute("DELETE FROM logs")

    add_user = [
        ("0268570643", "User1"),
        ("0369893411", "User2"),
        ("0371964595", "User3")
    ]

    add_item = [
        ("3911062411", "Item_ID_1", "Type 1", "Available", "Robot"),
        ("3911995531", "Item_ID_2", "Type 2", "Allocated", "Testing"),
        ("3911743371", "Item_ID_3", "Type 3", "Allocated", "Testing"),
        ("3910976139", "Item_ID_4", "Type 4", "Available", "Safe"),
        ("3910034315", "Item_ID_5", "Type 5", "Available", "Drawer"),
    ]

    cur.executemany("INSERT INTO user VALUES(?, ?)", add_user)
    cur.executemany("INSERT INTO inventory VALUES(?, ?, ?, ?, ?)", add_item)

    con.commit()
    con.close()
    print("Success! The database has been updated.")

if __name__ == "__main__":
    seed()