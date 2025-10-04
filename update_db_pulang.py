import sqlite3

DB_NAME = "database.db"

def update_database():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Cek kolom yang sudah ada
    cur.execute("PRAGMA table_info(absensi)")
    columns = [col[1] for col in cur.fetchall()]
    print(f"📋 Kolom saat ini: {columns}")
    
    # Tambah kolom baru jika belum ada
    if 'waktu_pulang' not in columns:
        cur.execute("ALTER TABLE absensi ADD COLUMN waktu_pulang TIMESTAMP")
        print("✅ Kolom 'waktu_pulang' ditambahkan")
    
    if 'status_pulang' not in columns:
        cur.execute("ALTER TABLE absensi ADD COLUMN status_pulang TEXT")
        print("✅ Kolom 'status_pulang' ditambahkan")
    
    if 'latitude_pulang' not in columns:
        cur.execute("ALTER TABLE absensi ADD COLUMN latitude_pulang REAL")
        print("✅ Kolom 'latitude_pulang' ditambahkan")
    
    if 'longitude_pulang' not in columns:
        cur.execute("ALTER TABLE absensi ADD COLUMN longitude_pulang REAL")
        print("✅ Kolom 'longitude_pulang' ditambahkan")
    
    conn.commit()
    conn.close()
    print("\n🎉 Database berhasil diupdate!")

if __name__ == "__main__":
    update_database()