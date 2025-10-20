import sqlite3

DB_NAME = "database.db"
conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE absensi ADD COLUMN bukti_surat TEXT")
    print("✅ Kolom 'bukti_surat' ditambahkan")
except:
    print("⚠️ Kolom 'bukti_surat' sudah ada")

conn.commit()
conn.close()