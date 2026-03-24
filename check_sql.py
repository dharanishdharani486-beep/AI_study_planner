import sqlite3
import os

DB_PATH = 'studycoach.db'

def check_sql():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='school_questions'")
    row = cursor.fetchone()
    if row:
        print("SQL for school_questions:\n", row[0])
    else:
        print("Table not found.")
    conn.close()

if __name__ == "__main__":
    check_sql()
