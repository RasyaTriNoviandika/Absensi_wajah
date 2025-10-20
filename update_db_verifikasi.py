# update_db_verifikasi.py - Tambah kolom verifikasi bukti surat
import sqlite3
from datetime import datetime

DB_NAME = "database.db"

def update_database():
    """Tambah kolom verifikasi untuk bukti surat"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        # Cek kolom yang sudah ada
        cur.execute("PRAGMA table_info(absensi)")
        columns = [col[1] for col in cur.fetchall()]
        print(f"📋 Kolom saat ini: {columns}\n")
        
        # Tambah kolom verifikasi_bukti
        if 'verifikasi_bukti' not in columns:
            cur.execute("ALTER TABLE absensi ADD COLUMN verifikasi_bukti TEXT")
            print("✅ Kolom 'verifikasi_bukti' ditambahkan")
        else:
            print("⚠️ Kolom 'verifikasi_bukti' sudah ada")
        
        # Tambah kolom verified_by
        if 'verified_by' not in columns:
            cur.execute("ALTER TABLE absensi ADD COLUMN verified_by TEXT")
            print("✅ Kolom 'verified_by' ditambahkan")
        else:
            print("⚠️ Kolom 'verified_by' sudah ada")
        
        # Tambah kolom verified_at
        if 'verified_at' not in columns:
            cur.execute("ALTER TABLE absensi ADD COLUMN verified_at TIMESTAMP")
            print("✅ Kolom 'verified_at' ditambahkan")
        else:
            print("⚠️ Kolom 'verified_at' sudah ada")
        
        conn.commit()
        
        # Verifikasi perubahan
        print("\n" + "="*60)
        print("VERIFIKASI STRUKTUR DATABASE")
        print("="*60)
        cur.execute("PRAGMA table_info(absensi)")
        all_columns = cur.fetchall()
        
        print("\n📊 Struktur tabel 'absensi' sekarang:")
        for col in all_columns:
            print(f"  • {col[1]} ({col[2]})")
        
        conn.close()
        print("\n🎉 Database berhasil diupdate!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("="*60)
    print("UPDATE DATABASE - VERIFIKASI BUKTI SURAT")
    print("="*60)
    print("\n⚠️ Script ini akan menambah kolom verifikasi ke tabel absensi:")
    print("   1. verifikasi_bukti (TEXT) - Status: APPROVED/REJECTED/NULL")
    print("   2. verified_by (TEXT) - Username admin yang verifikasi")
    print("   3. verified_at (TIMESTAMP) - Waktu verifikasi\n")
    
    update_database()