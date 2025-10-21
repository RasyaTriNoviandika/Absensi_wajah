import sqlite3
import math

DB_NAME = "database.db"

def hitung_jarak(lat1, lng1, lat2, lng2):
    """Hitung jarak antar koordinat (Haversine formula)"""
    R = 6371000  # Radius bumi dalam meter
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def debug_lokasi():
    """Debug masalah lokasi absensi"""
    
    print("=" * 80)
    print("DEBUG MASALAH LOKASI ABSENSI")
    print("=" * 80)
    
    # Koordinat dari error message Anda
    YOUR_LAT = -6.2635512  # Koordinat Anda saat coba absen
    YOUR_LNG = 106.9690768
    
    # Koordinat sekolah yang BENAR
    CORRECT_LAT = -6.2706589
    CORRECT_LNG = 106.9593685
    
    print("\n📍 KOORDINAT ANDA SAAT COBA ABSEN:")
    print(f"   Lat: {YOUR_LAT}, Long: {YOUR_LNG}")
    print(f"   🔗 https://www.google.com/maps?q={YOUR_LAT},{YOUR_LNG}")
    
    # Ambil koordinat dari database
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
        db_data = cur.fetchone()
        conn.close()
        
        if not db_data:
            print("\n❌ ERROR: Tidak ada data settings di database!")
            print("   Jalankan: python reset_koordinat_sekolah.py")
            return
        
        db_lat, db_lng, db_radius = db_data
        
        print("\n📍 KOORDINAT SEKOLAH DI DATABASE:")
        print(f"   Lat: {db_lat}, Long: {db_lng}")
        print(f"   Radius: {db_radius} meter")
        print(f"   🔗 https://www.google.com/maps?q={db_lat},{db_lng}")
        
        print("\n📍 KOORDINAT SEKOLAH YANG BENAR:")
        print(f"   Lat: {CORRECT_LAT}, Long: {CORRECT_LNG}")
        print(f"   🔗 https://www.google.com/maps?q={CORRECT_LAT},{CORRECT_LNG}")
        
        # Hitung jarak
        print("\n" + "=" * 80)
        print("ANALISIS JARAK")
        print("=" * 80)
        
        jarak_anda_ke_db = hitung_jarak(YOUR_LAT, YOUR_LNG, db_lat, db_lng)
        jarak_anda_ke_correct = hitung_jarak(YOUR_LAT, YOUR_LNG, CORRECT_LAT, CORRECT_LNG)
        jarak_db_ke_correct = hitung_jarak(db_lat, db_lng, CORRECT_LAT, CORRECT_LNG)
        
        print(f"\n1️⃣  Jarak Anda → Koordinat di Database:")
        print(f"   📏 {jarak_anda_ke_db:.0f} meter")
        if jarak_anda_ke_db <= db_radius:
            print(f"   ✅ DALAM RADIUS ({db_radius}m)")
        else:
            print(f"   ❌ DI LUAR RADIUS ({db_radius}m)")
        
        print(f"\n2️⃣  Jarak Anda → Koordinat Sekolah yang Benar:")
        print(f"   📏 {jarak_anda_ke_correct:.0f} meter")
        if jarak_anda_ke_correct <= db_radius:
            print(f"   ✅ DALAM RADIUS ({db_radius}m)")
        else:
            print(f"   ❌ DI LUAR RADIUS ({db_radius}m)")
        
        print(f"\n3️⃣  Jarak Koordinat Database → Koordinat yang Benar:")
        print(f"   📏 {jarak_db_ke_correct:.0f} meter")
        if jarak_db_ke_correct < 10:
            print(f"   ✅ KOORDINAT DATABASE SUDAH BENAR")
        else:
            print(f"   ❌ KOORDINAT DATABASE MASIH SALAH!")
        
        # Diagnosis
        print("\n" + "=" * 80)
        print("🔍 DIAGNOSIS")
        print("=" * 80)
        
        if jarak_db_ke_correct < 10:
            print("\n✅ Koordinat database SUDAH BENAR!")
            
            if jarak_anda_ke_correct <= db_radius:
                print("✅ Lokasi Anda juga DALAM RADIUS!")
                print("\n🤔 Tapi kenapa gagal absen?")
                print("   Kemungkinan:")
                print("   1. Aplikasi belum di-restart setelah update database")
                print("   2. Ada bug di kode pengecekan jarak")
                print("   3. Koordinat GPS HP tidak akurat")
                print("\n💡 SOLUSI:")
                print("   1. Restart aplikasi: Ctrl+C → python app.py")
                print("   2. Refresh halaman absensi di browser")
                print("   3. Pastikan GPS HP aktif dan akurat")
            else:
                print(f"❌ Lokasi Anda TERLALU JAUH dari sekolah!")
                print(f"   Jarak: {jarak_anda_ke_correct:.0f}m, Radius: {db_radius}m")
                print("\n💡 SOLUSI:")
                print("   1. Pastikan Anda benar-benar di lokasi sekolah")
                print("   2. Atau perbesar radius di admin panel")
                print("   3. Atau update koordinat sekolah ke lokasi yang benar")
        else:
            print("\n❌ KOORDINAT DATABASE MASIH SALAH!")
            print(f"   Selisih: {jarak_db_ke_correct:.0f} meter dari koordinat yang benar")
            print("\n💡 SOLUSI:")
            print("   1. Jalankan: python reset_koordinat_sekolah.py")
            print("   2. Restart aplikasi: Ctrl+C → python app.py")
            print("   3. Coba absen lagi")
        
        # Cek app.py constant
        print("\n" + "=" * 80)
        print("⚠️  CEK app.py")
        print("=" * 80)
        print("\nPastikan di app.py (baris 46-48) ada:")
        print("   SCHOOL_LAT = -6.2706589")
        print("   SCHOOL_LNG = 106.9593685")
        print("   RADIUS = 100")
        print("\nJangan ada koordinat lain yang aktif!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_lokasi()