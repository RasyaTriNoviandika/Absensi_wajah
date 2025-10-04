import sqlite3

DB_NAME = "database.db"

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

print("🔧 Menambahkan kolom baru...")

try:
    cur.execute("ALTER TABLE absensi ADD COLUMN waktu_pulang TIMESTAMP")
    print("✅ waktu_pulang ditambahkan")
except Exception as e:
    print(f"⚠️ waktu_pulang: {e}")

try:
    cur.execute("ALTER TABLE absensi ADD COLUMN status_pulang TEXT")
    print("✅ status_pulang ditambahkan")
except Exception as e:
    print(f"⚠️ status_pulang: {e}")

try:
    cur.execute("ALTER TABLE absensi ADD COLUMN latitude_pulang REAL")
    print("✅ latitude_pulang ditambahkan")
except Exception as e:
    print(f"⚠️ latitude_pulang: {e}")

try:
    cur.execute("ALTER TABLE absensi ADD COLUMN longitude_pulang REAL")
    print("✅ longitude_pulang ditambahkan")
except Exception as e:
    print(f"⚠️ longitude_pulang: {e}")

conn.commit()

# Verifikasi
cur.execute("PRAGMA table_info(absensi)")
columns = [col[1] for col in cur.fetchall()]
print(f"\n📋 Kolom sekarang: {columns}")

conn.close()
print("\n🎉 Selesai!")