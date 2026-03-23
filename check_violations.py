import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), 'studycoach.db')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT * FROM violations ORDER BY id DESC LIMIT 1').fetchall()
for row in rows:
    print(dict(row))
conn.close()
