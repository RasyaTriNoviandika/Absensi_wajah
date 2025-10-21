import sqlite3

DB_NAME = "database.db"

def reset_koordinat():
    """Reset koordinat sekolah ke lokasi BENAR"""
    
    print("=" * 70)
    print("RESET KOORDINAT SEKOLAH KE LOKASI YANG BENAR")
    print("=" * 70)
    
    # ============= ISI KOORDINAT SEKOLAH YANG BENAR DI SINI =============
    # Dapatkan dari Google Maps: Klik kanan lokasi sekolah → Copy koordinat
    
    SCHOOL_LAT = -6.2706589   # ← GANTI dengan koordinat sekolah yang BENAR
    SCHOOL_LNG = 106.9593685  # ← GANTI dengan koordinat sekolah yang BENAR
    RADIUS = 100              # ← Radius dalam meter (sesuaikan)
    
    print("\n📍 Koordinat yang akan disimpan:")
    print(f"   Latitude : {SCHOOL_LAT}")
    print(f"   Longitude: {SCHOOL_LNG}")
    print(f"   Radius   : {RADIUS} meter")
    
    # Konfirmasi
    print("\n⚠️  PENTING: Pastikan koordinat di atas BENAR!")
    print("   Cara cek:")
    print("   1. Buka Google Maps")
    print("   2. Klik kanan lokasi sekolah")
    print("   3. Pilih koordinat yang muncul (contoh: -6.2706589, 106.9593685)")
    print("   4. Paste di variabel SCHOOL_LAT dan SCHOOL_LNG di atas\n")
    
    response = input("Apakah koordinat sudah BENAR? (ketik 'yes' untuk lanjut): ")
    
    if response.lower() != 'yes':
        print("\n❌ Reset dibatalkan")
        print("📝 Edit file ini, ganti SCHOOL_LAT dan SCHOOL_LNG, lalu jalankan lagi")
        return
    
    # Proses update
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Cek data lama
    print("\n" + "=" * 70)
    print("KOORDINAT LAMA (SEBELUM UPDATE):")
    print("=" * 70)
    cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
    old = cur.fetchone()
    if old:
        print(f"📍 Latitude : {old[0]}")
        print(f"📍 Longitude: {old[1]}")
        print(f"📏 Radius   : {old[2]} meter")
    else:
        print("⚠️  Tidak ada data settings (akan dibuat baru)")
    
    # Update
    cur.execute("SELECT COUNT(*) FROM settings WHERE id=1")
    if cur.fetchone()[0] > 0:
        cur.execute("""
            UPDATE settings 
            SET latitude=?, longitude=?, radius=? 
            WHERE id=1
        """, (SCHOOL_LAT, SCHOOL_LNG, RADIUS))
    else:
        cur.execute("""
            INSERT INTO settings (id, latitude, longitude, radius) 
            VALUES (1, ?, ?, ?)
        """, (SCHOOL_LAT, SCHOOL_LNG, RADIUS))
    
    conn.commit()
    
    # Verifikasi
    print("\n" + "=" * 70)
    print("KOORDINAT BARU (SETELAH UPDATE):")
    print("=" * 70)
    cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
    new = cur.fetchone()
    print(f"📍 Latitude : {new[0]}")
    print(f"📍 Longitude: {new[1]}")
    print(f"📏 Radius   : {new[2]} meter")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ KOORDINAT SEKOLAH BERHASIL DIRESET!")
    print("=" * 70)
    print("\n📌 Langkah selanjutnya:")
    print("1. Restart aplikasi jika sedang berjalan")
    print("2. Login admin → Cek 'Peta Absensi'")
    print("3. Pastikan marker sekolah sudah benar")
    print("4. Coba absen dari lokasi sekolah")
    print("\n🔒 TIPS: Untuk mencegah berubah lagi:")
    print("   - Jangan bagikan password admin sembarangan")
    print("   - Backup database secara berkala")
    print("   - Monitor siapa yang akses admin panel")

if __name__ == "__main__":
    reset_koordinat()