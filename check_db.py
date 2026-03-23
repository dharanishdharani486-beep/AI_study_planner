import sqlite3
import os

DB_PATH = 'studycoach.db'

def check_tables():
    if not os.path.exists(DB_PATH):
        print(f"{DB_PATH} not found.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables found:", tables)
    
    if 'school_exams' in tables:
        print("SUCCESS: school_exams table exists!")
    else:
        print("ERROR: school_exams table MISSING.")
    
    conn.close()

if __name__ == "__main__":
    check_tables()
