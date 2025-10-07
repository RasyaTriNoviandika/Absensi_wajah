import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# 1️⃣ Buat tabel baru tanpa kolom foto_path
cur.execute("""
CREATE TABLE siswa_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    kelas TEXT NOT NULL,
    jurusan TEXT NOT NULL,
    wajah_file TEXT,
    encoding TEXT,
    nomor_absen TEXT
)
""")

# 2️⃣ Salin data lama yang masih ada
cur.execute("""
INSERT INTO siswa_new (id, nama, kelas, jurusan, wajah_file, encoding, nomor_absen)
SELECT id, nama, kelas, jurusan, NULL, encoding, nomor_absen FROM siswa
""")

# 3️⃣ Ganti tabel lama
cur.execute("DROP TABLE siswa")
cur.execute("ALTER TABLE siswa_new RENAME TO siswa")

conn.commit()
conn.close()

print("✅ Kolom 'foto_path' berhasil dihapus dan diganti dengan 'wajah_file'")
