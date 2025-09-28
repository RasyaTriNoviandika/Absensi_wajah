import sqlite3

DB_NAME = "database.db"

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

cur.execute("SELECT id, nama, kelas, jurusan, length(encoding) FROM siswa")
print(cur.fetchall())

conn.close()
