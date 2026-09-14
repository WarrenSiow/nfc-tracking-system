import sqlite3

def seed():
    con = sqlite3.connect("inventory.db")
    cur = con.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS inventory(rfid TEXT PRIMARY KEY, item_id TEXT, item_name TEXT, type TEXT, status TEXT, destination TEXT, access_level INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS user(id TEXT PRIMARY KEY, name TEXT, access_level INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS logs(timestamp TEXT, item_name TEXT, user_name TEXT, action TEXT)")
    
    cur.execute("DELETE FROM inventory")
    cur.execute("DELETE FROM user")
    cur.execute("DELETE FROM logs")

    add_user = [
        ("0268570643", "User1", 1),
        ("0369893411", "User2", 2),
        ("0371964595", "User3", 3)
    ]

    add_item = [
        ("3911062411", "Item_ID_1", "Item 1", "Type 1", "In Storage", "Destination 1", 2),
        ("3911995531", "Item_ID_2", "Item 2", "Type 2", "In Storage", "Destination 2", 3),
        ("3911743371", "Item_ID_3", "Item 3", "Type 3", "In Storage", "Destination 3", 2),
        ("3910976139", "Item_ID_4", "Item 4", "Type 4", "In Storage", "Destination 4", 1),
        ("3910034315", "Item_ID_5", "Item 5", "Type 5", "In Storage", "Destination 5", 1),
    ]

    cur.executemany("INSERT INTO user VALUES(?, ?, ?)", add_user)
    cur.executemany("INSERT INTO inventory VALUES(?, ?, ?, ?, ?, ?, ?)", add_item)

    con.commit()
    con.close()
    print("Success! The database has been updated.")

if __name__ == "__main__":
    seed()