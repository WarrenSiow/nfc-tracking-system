# status = ["Available", "Allocated", "Repairing", "Lending"]
# return_destination = ["Safe", "Drawer"]
# borrow_destination = ["Robot", "Testing"]

import sqlite3

def seed():
    con = sqlite3.connect("inventory.db")
    cur = con.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS inventory(rfid TEXT PRIMARY KEY, item_id TEXT, status TEXT, current_location TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS user(id TEXT PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS logs(timestamp TEXT, item_id TEXT, user_name TEXT, action TEXT)")
    
    cur.execute("DELETE FROM inventory")
    cur.execute("DELETE FROM user")
    cur.execute("DELETE FROM logs")

    add_user = [
        ("3385569875", "PEH WEN YI A25KE5003"),
        ("3384783443", "WARREN SIOW JUIN WEI A25KM0367"),
        ("3360865363", "GOH KAH KIAT A24KE0093"),
    ]

    add_item = [
        ("3384359507", "PM-DLASER-07", "Available", "Safe"),
        ("3383876691", "PH-JTSN-02", "Available", "Safe"),
        ("3376875091", "PH-JTSN-03", "Available", "Safe"),
        ("3377336915", "PH-JTSN-04", "Available", "Safe"),
        ("3372646483", "PH-LDR-01", "Available", "Safe"),
        ("3376015443", "PH-LDR-04", "Available", "Safe"),
        ("3372175443", "PH-LDR-05", "Available", "Safe"),
        ("3383444051", "PH-LDR-06", "Available", "Safe"),
        ("3373199187", "PH-LDR-08", "Available", "Safe"),
        ("3382628691", "PH-JTSN-01", "Available", "Safe"),
        ("3379426899", "PM-DLASER-01", "Available", "Safe"),
        ("3378969427", "PM-DLASER-02", "Available", "Safe"),
        ("3379949651", "PM-DLASER-03", "Available", "Safe"),
        ("3380401747", "PM-DLASER-04", "Available", "Safe"),
        ("3381236563", "PM-DLASER-05", "Available", "Safe"),
        ("3381683283", "PM-DLASER-06", "Available", "Safe"),
        ("3378120019", "PH-MBUS-01", "Available", "Safe"),
        ("3385981523", "PH-MBUS-02", "Available", "Safe"),
        ("3377720659", "PH-BMBUS", "Available", "Safe"),
        ("3375547219", "PH-CAM-01", "Available", "Safe"),
        ("3373668435", "PH-CAM-02", "Available", "Safe"),
        ("3363966291", "PM-TOF-01", "Available", "Safe"),
        ("3363116883", "PM-TOF-02", "Available", "Safe"),
        ("3364423763", "PM-TOF-03", "Available", "Safe"),
        ("3362664019", "PM-TOF-04", "Available", "Safe"),
        ("3375003475", "PM-TOF-05", "Available", "Safe"),
        ("3371305299", "PM-GEN-01", "Available", "Safe"),
        ("3372251219", "PM-GEN-02", "Available", "Safe"),
        ("3370758483", "PH-XSNSR-01", "Available", "Safe"),
        ("3370285395", "PH-OLASER-01", "Available", "Safe"),
        ("3369813331", "PH-OLASER-03", "Available", "Safe"),
        ("3368942419", "PH-OLASER-04", "Available", "Safe"),
        ("3368473171", "PH-OLASER-05", "Available", "Safe"),
        ("3368088403", "PH-OLASER-06", "Available", "Safe"),
        ("3364958291", "PH-GLASER-01", "Available", "Safe"),
        ("3366279763", "PH-GLASER-02", "Available", "Safe"),
        ("3367683667", "PH-GLASER-03", "Available", "Safe"),
        ("3365419603", "PH-GLASER-04", "Available", "Safe"),
        ("3366819155", "PH-GLASER-05", "Available", "Safe"),
        ("3366747987", "PH-GLASER-06", "Available", "Safe"),
        ("3362145619", "PH-MB-01", "Available", "Safe"),
        ("3361697107", "PH-GPU-01", "Available", "Safe"),
        ("HELLO", "Item_ID_5", "Available", "Safe"),

    ]

    cur.executemany("INSERT INTO user VALUES(?, ?)", add_user)
    cur.executemany("INSERT INTO inventory VALUES(?, ?, ?, ?)", add_item)

    con.commit()
    con.close()
    print("Success! The database has been updated.")

if __name__ == "__main__":
    seed()