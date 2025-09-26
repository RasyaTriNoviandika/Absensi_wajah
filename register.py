import sqlite3
import cv2
import os

DB_NAME = "database.db"
FACES_DIR = "faces"  # folder untuk simpan foto wajah

def buat_tabel():
    """Buat tabel siswa jika belum ada"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS siswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            kelas TEXT NOT NULL,
            jurusan TEXT NOT NULL,
            foto_path TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def register_siswa(nama, kelas, jurusan, foto_path):
    """Simpan data siswa ke database"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO siswa (nama, kelas, jurusan, foto_path) VALUES (?, ?, ?, ?)",
                (nama, kelas, jurusan, foto_path))
    conn.commit()
    conn.close()
    print(f"✅ Data siswa '{nama}' berhasil disimpan dengan foto: {foto_path}")

def buka_kamera(index=0):
    """Coba buka kamera dengan beberapa backend"""
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            return cap
        cap.release()
    return None

def capture_wajah(nama):
    """Ambil foto wajah siswa"""
    if not os.path.exists(FACES_DIR):
        os.makedirs(FACES_DIR)

    cap = buka_kamera()

    if not cap or not cap.isOpened():
        print("❌ Kamera tidak bisa dibuka")
        return None

    print("📸 Tekan [SPACE] untuk mengambil foto, [ESC] untuk batal.")
    foto_path = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Gagal mengambil frame dari kamera")
            break

        cv2.imshow("Register Wajah", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            print("❌ Batal ambil foto.")
            break
        elif key == 32:  # SPACE
            foto_path = os.path.join(FACES_DIR, f"{nama}.jpg")
            cv2.imwrite(foto_path, frame)
            print(f"✅ Foto tersimpan di {foto_path}")
            break

    cap.release()
    cv2.destroyAllWindows()
    return foto_path

# if __name__ == "__main__":
#     buat_tabel()
#     print("=== Register Wajah Siswa ===")
#     nama = input("Nama     : ").strip()
#     kelas = input("Kelas    : ").strip()
#     jurusan = input("Jurusan  : ").strip()

    # if nama and kelas and jurusan:
    #     foto_path = capture_wajah(nama)
    #     if foto_path:
    #         register_siswa(nama, kelas, jurusan, foto_path)
    # else:r
    #     print("❌ Semua field harus diisi!")
