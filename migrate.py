import sqlite3
import os
DB_PATH = os.path.join(os.path.dirname(__file__), 'studycoach.db')
if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('ALTER TABLE users RENAME COLUMN phone TO email;')
        print("Renamed users table phone to email")
    except Exception as e:
        print(f"Migration error: {e}")
    conn.commit()
    conn.close()
else:
    print("DB does not exist.")
