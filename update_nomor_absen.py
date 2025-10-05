# update_nomor_absen.py - Script untuk menambah kolom nomor_absen (FIXED)
import sqlite3
from datetime import datetime
import shutil
import os

DB_NAME = "database.db"

def backup_database():
    """Backup database sebelum diubah"""
    if not os.path.exists(DB_NAME):
        print(f"❌ Database {DB_NAME} tidak ditemukan!")
        return False
    
    backup_name = f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy(DB_NAME, backup_name)
    print(f"✅ Backup database dibuat: {backup_name}")
    return True

def update_schema():
    """Tambah kolom nomor_absen ke tabel siswa - FIXED VERSION"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        # Cek apakah kolom sudah ada
        cur.execute("PRAGMA table_info(siswa)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'nomor_absen' in columns:
            print("⚠️ Kolom 'nomor_absen' sudah ada!")
            conn.close()
            return True
        
        print("📝 Menambahkan kolom 'nomor_absen'...")
        
        # ============= FIX: Tambah kolom TANPA UNIQUE constraint =============
        # SQLite tidak support ALTER TABLE ADD COLUMN dengan UNIQUE
        # Kita tambah dulu tanpa UNIQUE, lalu buat index unique setelahnya
        cur.execute("ALTER TABLE siswa ADD COLUMN nomor_absen TEXT")
        print("✅ Kolom 'nomor_absen' berhasil ditambahkan!")
        
        # Generate nomor absen untuk siswa yang sudah ada
        print("\n📋 Generating nomor absen untuk siswa existing...")
        generate_existing_nomor_absen(cur)
        conn.commit()
        
        # Buat UNIQUE index setelah data diisi
        print("\n🔒 Membuat UNIQUE constraint untuk nomor_absen...")
        try:
            cur.execute("CREATE UNIQUE INDEX idx_nomor_absen ON siswa(nomor_absen)")
            print("✅ UNIQUE constraint berhasil dibuat!")
        except sqlite3.IntegrityError as e:
            print(f"⚠️ Warning: Ada duplikasi nomor absen. Index unique tidak dibuat.")
            print(f"   Detail: {e}")
        
        conn.commit()
        conn.close()
        print("\n🎉 Update database selesai!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_existing_nomor_absen(cur):
    """Generate nomor absen untuk siswa yang sudah terdaftar"""
    # Ambil semua siswa existing
    cur.execute("SELECT id, nama, kelas, jurusan FROM siswa ORDER BY id")
    siswa_list = cur.fetchall()
    
    if not siswa_list:
        print("   ℹ️  Tidak ada siswa existing, skip generate nomor")
        return
    
    print(f"   📊 Ditemukan {len(siswa_list)} siswa existing")
    
    # Kelompokkan per kelas-jurusan untuk numbering
    kelompok = {}
    for sid, nama, kelas, jurusan in siswa_list:
        key = f"{kelas}-{jurusan}"
        if key not in kelompok:
            kelompok[key] = []
        kelompok[key].append((sid, nama))
    
    print(f"   📊 Ditemukan {len(kelompok)} kelompok kelas-jurusan\n")
    
    # Generate nomor untuk setiap kelompok
    total_updated = 0
    for key, siswa in kelompok.items():
        print(f"   📝 {key}:")
        for idx, (sid, nama) in enumerate(siswa, start=1):
            nomor_absen = f"{key}-{idx:03d}"
            cur.execute("UPDATE siswa SET nomor_absen = ? WHERE id = ?", (nomor_absen, sid))
            print(f"      ✅ {nama}: {nomor_absen}")
            total_updated += 1
        print()  # Empty line between groups
    
    print(f"   ✅ Total {total_updated} siswa diberi nomor absen\n")

def verify_update():
    """Verifikasi update berhasil"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        # Cek kolom
        cur.execute("PRAGMA table_info(siswa)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'nomor_absen' not in columns:
            print("\n❌ Verifikasi gagal: Kolom 'nomor_absen' tidak ditemukan")
            conn.close()
            return False
        
        print("\n" + "="*60)
        print("VERIFIKASI HASIL UPDATE")
        print("="*60)
        
        print("✅ Kolom 'nomor_absen' berhasil ditambahkan")
        
        # Cek data
        cur.execute("SELECT COUNT(*) FROM siswa")
        total_siswa = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM siswa WHERE nomor_absen IS NOT NULL")
        count_with_nomor = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM siswa WHERE nomor_absen IS NULL")
        count_without_nomor = cur.fetchone()[0]
        
        print(f"✅ Total siswa: {total_siswa}")
        print(f"✅ Siswa dengan nomor absen: {count_with_nomor}")
        
        if count_without_nomor > 0:
            print(f"⚠️  Siswa tanpa nomor absen: {count_without_nomor}")
        
        # Cek duplikasi
        cur.execute("""
            SELECT nomor_absen, COUNT(*) as cnt 
            FROM siswa 
            WHERE nomor_absen IS NOT NULL
            GROUP BY nomor_absen 
            HAVING cnt > 1
        """)
        duplicates = cur.fetchall()
        
        if duplicates:
            print(f"\n⚠️  Ditemukan {len(duplicates)} nomor absen duplikat:")
            for nomor, count in duplicates:
                print(f"   - {nomor}: {count}x")
        else:
            print("✅ Tidak ada nomor absen duplikat")
        
        # Tampilkan sample data per kelas
        print("\n" + "="*60)
        print("SAMPLE DATA (5 siswa pertama per kelas)")
        print("="*60)
        
        cur.execute("SELECT DISTINCT kelas, jurusan FROM siswa ORDER BY kelas, jurusan")
        kelas_list = cur.fetchall()
        
        for kelas, jurusan in kelas_list:
            print(f"\n📚 {kelas} - {jurusan}:")
            cur.execute("""
                SELECT nama, nomor_absen 
                FROM siswa 
                WHERE kelas = ? AND jurusan = ?
                ORDER BY nomor_absen
                LIMIT 5
            """, (kelas, jurusan))
            
            rows = cur.fetchall()
            if rows:
                for nama, nomor in rows:
                    print(f"   • {nomor}: {nama}")
            else:
                print("   (Tidak ada siswa)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error saat verifikasi: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_statistics():
    """Tampilkan statistik nomor absen per kelas"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        print("\n" + "="*60)
        print("STATISTIK NOMOR ABSEN PER KELAS")
        print("="*60)
        
        cur.execute("""
            SELECT kelas, jurusan, COUNT(*) as total
            FROM siswa
            WHERE nomor_absen IS NOT NULL
            GROUP BY kelas, jurusan
            ORDER BY kelas, jurusan
        """)
        
        stats = cur.fetchall()
        
        if stats:
            total_all = 0
            for kelas, jurusan, count in stats:
                print(f"📊 {kelas}-{jurusan}: {count} siswa")
                total_all += count
            print(f"\n✅ Total keseluruhan: {total_all} siswa")
        else:
            print("ℹ️  Belum ada siswa terdaftar")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error saat menampilkan statistik: {e}")

if __name__ == "__main__":
    print("="*60)
    print("UPDATE DATABASE - TAMBAH NOMOR ABSEN (FIXED VERSION)")
    print("="*60)
    print("\n⚠️  PENTING: Script ini akan mengubah struktur database!")
    print("✅ Backup otomatis akan dibuat sebelum perubahan")
    print("\nYang akan dilakukan:")
    print("1. Backup database ke file terpisah")
    print("2. Tambah kolom 'nomor_absen' ke tabel siswa")
    print("3. Generate nomor absen untuk siswa yang sudah ada")
    print("4. Buat UNIQUE constraint untuk mencegah duplikasi")
    print("5. Verifikasi hasil update\n")
    
    response = input("Lanjutkan update? (ketik 'yes' untuk lanjut): ")
    
    if response.lower() == 'yes':
        print("\n" + "="*60)
        print("MEMULAI UPDATE...")
        print("="*60 + "\n")
        
        # Step 1: Backup
        if not backup_database():
            print("\n❌ Backup gagal! Update dibatalkan.")
            exit(1)
        
        # Step 2: Update schema
        if not update_schema():
            print("\n❌ Update gagal! Periksa error di atas.")
            print("ℹ️  Database backup tersimpan, Anda bisa restore jika perlu.")
            exit(1)
        
        # Step 3: Verify
        if not verify_update():
            print("\n⚠️  Verifikasi gagal, tapi update mungkin berhasil.")
            print("ℹ️  Silakan cek manual database Anda.")
        
        # Step 4: Show statistics
        show_statistics()
        
        print("\n" + "="*60)
        print("✅ UPDATE SELESAI!")
        print("="*60)
        print("\n📌 Langkah selanjutnya:")
        print("1. Update kode app.py sesuai instruksi")
        print("2. Update templates HTML")
        print("3. Restart aplikasi: python app.py")
        print("4. Test registrasi siswa baru")
        print("\n✅ Database siap digunakan dengan nomor absen!")
        
    else:
        print("\n❌ Update dibatalkan")