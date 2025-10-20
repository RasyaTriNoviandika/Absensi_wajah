import sqlite3

DB_NAME = "database.db"

def update_database():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Cek kolom yang sudah ada
    cur.execute("PRAGMA table_info(absensi)")
    columns = [col[1] for col in cur.fetchall()]
    
    # Tambah kolom alasan_pulang jika belum ada
    if 'alasan_pulang' not in columns:
        cur.execute("ALTER TABLE absensi ADD COLUMN alasan_pulang TEXT")
        print("✅ Kolom 'alasan_pulang' berhasil ditambahkan!")
    else:
        print("⚠️ Kolom 'alasan_pulang' sudah ada")
    
    conn.commit()
    conn.close()
    print("🎉 Database berhasil diupdate!")

if __name__ == "__main__":
    update_database()