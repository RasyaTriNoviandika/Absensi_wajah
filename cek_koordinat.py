import sqlite3
import os

DB_NAME = "database.db"

def cek_koordinat():
    """Cek koordinat area absensi yang tersimpan di database"""
    
    if not os.path.exists(DB_NAME):
        print(f"❌ File {DB_NAME} tidak ditemukan!")
        print(f"📂 Lokasi sekarang: {os.getcwd()}")
        return
    
    print("=" * 70)
    print("CEK KOORDINAT AREA ABSENSI")
    print("=" * 70)
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        # Cek apakah tabel settings ada
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if not cur.fetchone():
            print("\n⚠️  Tabel 'settings' belum ada di database!")
            print("    Jalankan aplikasi sekali untuk membuat tabel.")
            conn.close()
            return
        
        # Ambil koordinat
        cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
        result = cur.fetchone()
        
        if not result:
            print("\n⚠️  Belum ada data koordinat di database!")
            print("    Koordinat akan dibuat otomatis saat aplikasi dijalankan.")
            conn.close()
            return
        
        lat, lng, radius = result
        
        # Koordinat yang BENAR (referensi)
        CORRECT_LAT = -6.2706589
        CORRECT_LNG = 106.9593685
        
        # Koordinat yang SALAH (referensi)
        WRONG_LAT = -6.2635512
        WRONG_LNG = 106.9690768
        
        print("\n📍 KOORDINAT SAAT INI DI DATABASE:")
        print("-" * 70)
        print(f"   Latitude  : {lat}")
        print(f"   Longitude : {lng}")
        print(f"   Radius    : {radius} meter")
        
        # Cek apakah koordinat benar atau salah
        print("\n🔍 STATUS KOORDINAT:")
        print("-" * 70)
        
        # Hitung selisih dengan koordinat yang benar
        diff_correct = abs(lat - CORRECT_LAT) + abs(lng - CORRECT_LNG)
        diff_wrong = abs(lat - WRONG_LAT) + abs(lng - WRONG_LNG)
        
        if diff_correct < 0.0001:
            print("   ✅ KOORDINAT BENAR!")
            print("   ✅ Ini koordinat SMKN 9 Bekasi yang sudah ditest")
            print("   ✅ Absensi seharusnya bisa dilakukan dari sekolah")
        elif diff_wrong < 0.0001:
            print("   ❌ KOORDINAT SALAH!")
            print("   ❌ Ini bukan koordinat sekolah yang benar")
            print("   ❌ Perlu diupdate ke koordinat yang benar")
            print("\n   💡 Jalankan: python fix_lokasi_sekolah.py")
        else:
            print("   ⚠️  KOORDINAT TIDAK DIKENALI!")
            print("   ⚠️  Ini bukan koordinat yang seharusnya")
        
        # Tampilkan perbandingan
        print("\n📊 PERBANDINGAN KOORDINAT:")
        print("-" * 70)
        print("KOORDINAT SAAT INI:")
        print(f"  📍 {lat}, {lng}")
        print(f"  🔗 https://www.google.com/maps?q={lat},{lng}")
        
        print("\nKOORDINAT YANG BENAR (SMKN 9 Bekasi):")
        print(f"  ✅ {CORRECT_LAT}, {CORRECT_LNG}")
        print(f"  🔗 https://www.google.com/maps?q={CORRECT_LAT},{CORRECT_LNG}")
        
        print("\nKOORDINAT YANG SALAH (lokasi lain):")
        print(f"  ❌ {WRONG_LAT}, {WRONG_LNG}")
        print(f"  🔗 https://www.google.com/maps?q={WRONG_LAT},{WRONG_LNG}")
        
        # Tips
        print("\n" + "=" * 70)
        print("💡 TIPS:")
        print("-" * 70)
        print("1. Buka link Google Maps di atas untuk verifikasi")
        print("2. Link yang benar harus mengarah ke lokasi sekolah")
        print("3. Jika koordinat salah, jalankan: python fix_lokasi_sekolah.py")
        print("4. Setelah fix, cek lagi dengan: python cek_koordinat.py")
        
        # Cek total siswa (bonus info)
        cur.execute("SELECT COUNT(*) FROM siswa")
        total_siswa = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM absensi WHERE DATE(waktu) = DATE('now', 'localtime')")
        absen_hari_ini = cur.fetchone()[0]
        
        print("\n📊 INFO TAMBAHAN:")
        print("-" * 70)
        print(f"   Total siswa terdaftar   : {total_siswa}")
        print(f"   Absensi hari ini        : {absen_hari_ini}")
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ Pengecekan selesai!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    cek_koordinat()