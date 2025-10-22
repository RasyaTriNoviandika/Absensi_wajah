# =================== UPDATE app.py - PERBAIKAN DUPLIKASI REGISTRASI ===================
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3, math, os, uuid, face_recognition
from datetime import datetime, timedelta
from flask import send_file
import pandas as pd
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from werkzeug.security import generate_password_hash, check_password_hash
import ast
import secrets
import os
import numpy as np
from flask import send_from_directory
from functools import wraps
import time

# ============= KONSTANTA & FUNGSI HELPER HARUS DI ATAS! =============
SECRET_KEY_FILE = '.secret_key'

def get_or_create_secret_key():
    """Generate or load persistent secret key"""
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, 'r') as f:
            return f.read().strip()
    else:
        key = secrets.token_hex(32)
        with open(SECRET_KEY_FILE, 'w') as f:
            f.write(key)
        print(f"✅ New secret key created: {SECRET_KEY_FILE}")
        return key

# ============= BARU BISA BUAT APP =============
app = Flask(__name__)

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # Gunakan memory storage (simple)
)

print("✅ Rate limiter activated!")

# ============= KONFIGURASI KEAMANAN =============
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or get_or_create_secret_key()
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'

# ---------------- Konstanta Default ----------------
SCHOOL_LAT = -6.2706589
SCHOOL_LNG = 106.9593685
RADIUS = 50

# SCHOOL_LAT = -6.2706589
# SCHOOL_LNG = 106.9593685
# RADIUS = 1500  # ubah dari 100 ke 1500 meter

# SCHOOL_LAT = -6.2635512
# SCHOOL_LNG = 106.9690768
# RADIUS = 50

DB_NAME = "database.db"
FACES_DIR = "faces"
UPLOAD_DIR = "uploads"

# Buat folder upload jika belum ada
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Face Recognition Thresholds
FACE_RECOGNITION_THRESHOLD = 0.42
FACE_DUPLICATE_THRESHOLD = 0.4

# Maximum upload file size: 5MB
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Allowed extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

def monitor_performance(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        end_time = time.time()
        
        duration = end_time - start_time
        app.logger.info(f"⏱️ {f.__name__} executed in {duration:.2f}s")
        
        return result
    return decorated_function

def get_settings():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
    result = cur.fetchone()
    conn.close()
    return result or (-6.2635512, 106.9690768, 50)  # default

@app.route("/update_settings", methods=["POST"])
def update_settings():
    lat = float(request.form["latitude"])
    lng = float(request.form["longitude"])
    radius = int(request.form["radius"])

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE settings SET latitude=?, longitude=?, radius=? WHERE id=1", (lat, lng, radius))
    conn.commit()
    conn.close()

    flash("Pengaturan lokasi berhasil diperbarui!", "success")
    return redirect("/pengaturan")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_upload_file(file):
    """Validate uploaded file"""
    if not file or file.filename == '':
        return False, "File tidak boleh kosong"
    
    if not allowed_file(file.filename):
        return False, "Format file tidak didukung! Gunakan JPG, JPEG, atau PNG"
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > app.config['MAX_CONTENT_LENGTH']:
        return False, "Ukuran file terlalu besar! Maksimal 5MB"
    
    return True, "OK"

# Biar tabel siswa otmatis

def ensure_database_structure():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    print("🔍 Memeriksa dan memperbaiki struktur database...")

    # ===== Tabel siswa =====
    cur.execute("PRAGMA table_info(siswa)")
    siswa_columns = [c[1] for c in cur.fetchall()]

    if "wajah_file" not in siswa_columns:
        try:
            cur.execute("ALTER TABLE siswa ADD COLUMN wajah_file TEXT")
            print("✅ Kolom wajah_file ditambahkan ke tabel siswa")
        except Exception as e:
            print(f"⚠️ wajah_file: {e}")

    if "encoding" not in siswa_columns:
        try:
            cur.execute("ALTER TABLE siswa ADD COLUMN encoding BLOB")
            print("✅ Kolom encoding ditambahkan ke tabel siswa")
        except Exception as e:
            print(f"⚠️ encoding: {e}")

    # ===== Tabel absensi =====
    cur.execute("PRAGMA table_info(absensi)")
    absensi_columns = [c[1] for c in cur.fetchall()]

    def add_column_if_missing(column_name, column_type):
        if column_name not in absensi_columns:
            try:
                cur.execute(f"ALTER TABLE absensi ADD COLUMN {column_name} {column_type}")
                print(f"✅ Kolom {column_name} ditambahkan ke tabel absensi")
            except Exception as e:
                print(f"⚠️ {column_name}: {e}")

    add_column_if_missing("waktu_pulang", "TIMESTAMP")
    add_column_if_missing("status_pulang", "TEXT")
    add_column_if_missing("latitude_pulang", "REAL")
    add_column_if_missing("longitude_pulang", "REAL")
    add_column_if_missing("alasan_pulang", "TEXT")

    conn.commit()
    conn.close()
    print("🎉 Pemeriksaan struktur database selesai!\n")

# Jalankan otomatis saat startup Flask
ensure_database_structure()
# ============= PASTIKAN STRUKTUR DATABASE =============

def ensure_db_structure():
    """Pastikan tabel absensi memiliki kolom lengkap"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Cek apakah tabel absensi sudah ada
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='absensi';")
    if not cur.fetchone():
        print("⚠️ Tabel 'absensi' belum ada. Jalankan migrasi atau seeding terlebih dahulu.")
        conn.close()
        return

    # Ambil semua kolom yang sudah ada
    cur.execute("PRAGMA table_info(absensi);")
    existing_cols = [row[1] for row in cur.fetchall()]

    # Kolom wajib
    required_cols = {
        "waktu_pulang": "TEXT",
        "status_pulang": "TEXT",
        "latitude_pulang": "TEXT",
        "longitude_pulang": "TEXT",
        "alasan_pulang": "TEXT"
    }

    # Tambahkan kolom yang belum ada
    for col, col_type in required_cols.items():
        if col not in existing_cols:
            try:
                cur.execute(f"ALTER TABLE absensi ADD COLUMN {col} {col_type};")
                print(f"✅ Kolom '{col}' berhasil ditambahkan.")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Gagal menambahkan kolom {col}: {e}")

    conn.commit()
    conn.close()
    print("🎉 Struktur tabel absensi sudah dicek & diperbarui otomatis!")


ensure_db_structure()

# ============= FUNGSI VERIFIKASI & STATISTIK NOMOR ABSEN =============

def login_required(f):
    """Decorator untuk memastikan admin sudah login"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def buat_admin_default():
    """Buat akun admin default jika belum ada"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Cek apakah tabel admin sudah ada
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Cek apakah sudah ada admin
    cur.execute("SELECT COUNT(*) FROM admin")
    count = cur.fetchone()[0]
    
    if count == 0:
        # Buat admin default: username=admin, password=admin123
        password_hash = generate_password_hash('guru_sija23')
        cur.execute(
            "INSERT INTO admin (username, password_hash) VALUES (?, ?)",
            ('admin', password_hash)
        )
        conn.commit()
        # print("✅ Admin default dibuat - Username: admin, Password: gurusija")
    
    conn.close()

# Simpan foto
@app.route('/faces/<filename>')
def serve_face(filename):
    return send_from_directory('faces', filename)

@app.route("/generate_dummy")
@login_required
def generate_dummy():
    """Generate 20 siswa dummy + absensi bervariasi (hadir, belum pulang, pulang cepat, tepat waktu)"""
    import random, math

    conn = sqlite3.connect(DB_NAME, timeout=10)
    cur = conn.cursor()

    print("🧠 Membuat data dummy lengkap (20 siswa)...")

    # ====================== DATA SISWA ======================
    nama_depan = ["Ahmad", "Budi", "Cahya", "Dani", "Eka", "Fajar", "Gita", "Hadi", "Indra", "Joko", 
                  "Kartika", "Lina", "Maya", "Nur", "Oktavia", "Putra", "Rani", "Siti", "Teguh", "Umar"]
    nama_belakang = ["Pratama", "Sari", "Wijaya", "Kusuma", "Permana", "Putri", "Santoso", "Ramadhan", "Hidayat", "Lestari"]
    kelas_list = ["X", "XI", "XII"]
    jurusan_list = ["SIJA1", "SIJA2", "DKV1", "PB1"]

    cur.execute("DELETE FROM siswa")
    cur.execute("DELETE FROM absensi")
    conn.commit()

    siswa_ids = []
    for i in range(1, 21):
        nama = f"{random.choice(nama_depan)} {random.choice(nama_belakang)}"
        kelas = random.choice(kelas_list)
        jurusan = random.choice(jurusan_list)
        nomor_absen = f"{kelas}-{jurusan}-{i:03d}"
        cur.execute("""
            INSERT INTO siswa (nama, kelas, jurusan, wajah_file, encoding, nomor_absen)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nama, kelas, jurusan, "dummy.jpg", "[]", nomor_absen))
        siswa_ids.append((cur.lastrowid, nama, kelas, jurusan))
    conn.commit()

    # ====================== ABSENSI HARI INI ======================
    now = datetime.utcnow() + timedelta(hours=7)
    tanggal = now.date()
    alasan_list = [
        "izin pulang karna mau tidur",
        "Izin ke dokter",
        "Keperluan keluarga",
        "Ada acara mendadak",
        "Izin mau pulang karna mau tidur"
    ]

    for sid, nama, kelas, jurusan in siswa_ids:
        rand = random.random()
        lat = SCHOOL_LAT + random.uniform(-0.0002, 0.0002)
        lng = SCHOOL_LNG + random.uniform(-0.0002, 0.0002)

        # 20% belum absen
        if rand < 0.2:
            continue

        # Absen masuk
        jam_masuk = random.randint(6, 8)
        menit_masuk = random.randint(0, 59)
        waktu_masuk = now.replace(hour=jam_masuk, minute=menit_masuk, second=0)
        status_masuk = "HADIR" if jam_masuk < 7 or (jam_masuk == 7 and menit_masuk <= 30) else "TERLAMBAT"

        cur.execute("""
            INSERT INTO absensi (siswa_id, nama, kelas, jurusan, latitude, longitude, status, waktu)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, nama, kelas, jurusan, lat, lng, status_masuk, waktu_masuk))
        absen_id = cur.lastrowid

        # 30% belum pulang
        if rand < 0.5:
            continue

        # Sisanya pulang
        jam_pulang = random.randint(14, 16)
        menit_pulang = random.randint(0, 59)
        waktu_pulang = now.replace(hour=jam_pulang, minute=menit_pulang, second=0)

        if jam_pulang < 15:
            status_pulang = "PULANG CEPAT"
            alasan = random.choice(alasan_list)
        elif jam_pulang <= 16:
            status_pulang = "PULANG TEPAT WAKTU"
            alasan = ""
        else:
            status_pulang = "PULANG TERLAMBAT"
            alasan = ""

        cur.execute("""
            UPDATE absensi 
            SET waktu_pulang=?, status_pulang=?, latitude_pulang=?, longitude_pulang=?, alasan_pulang=?
            WHERE id=?
        """, (waktu_pulang, status_pulang, lat, lng, alasan, absen_id))

    conn.commit()
    conn.close()

    print("🎉 Dummy berhasil dibuat: 20 siswa dengan data variasi hadir/pulang.")
    flash("✅ 20 Data dummy berhasil dibuat dengan variasi status absensi.", "success")
    return redirect(url_for("admin_analytics"))
# ---------------- Database ----------------
def buat_tabel():
    """Membuat tabel utama jika belum ada dan menambahkan kolom baru jika perlu"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # ===================== TABEL SISWA =====================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS siswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            kelas TEXT NOT NULL,
            jurusan TEXT NOT NULL,
            foto_path TEXT NOT NULL,
            encoding TEXT
        )
    """)

    # Pastikan kolom nomor_absen ada
    cur.execute("PRAGMA table_info(siswa)")
    kolom_siswa = [r[1] for r in cur.fetchall()]
    if "nomor_absen" not in kolom_siswa:
        cur.execute("ALTER TABLE siswa ADD COLUMN nomor_absen TEXT")
        print("✅ Kolom 'nomor_absen' ditambahkan ke tabel siswa")

    # ===================== TABEL ABSENSI =====================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS absensi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            siswa_id INTEGER,
            nama TEXT NOT NULL,
            kelas TEXT NOT NULL,
            jurusan TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            status TEXT NOT NULL,
            waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ===================== TABEL SETTINGS =====================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL,
            longitude REAL,
            radius INTEGER
        )
    """)

    # Isi default area absensi jika kosong
    cur.execute("SELECT COUNT(*) FROM settings")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO settings (latitude, longitude, radius) VALUES (?, ?, ?)",
            (SCHOOL_LAT, SCHOOL_LNG, RADIUS)
        )

    conn.commit()
    conn.close()
    print("🎉 Database siap digunakan!")

def auto_migrate_database():
    """Auto-migrate database schema untuk kolom pulang"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        # Cek kolom yang ada
        cur.execute("PRAGMA table_info(absensi)")
        columns = [col[1] for col in cur.fetchall()]
        
        print(f"📋 Kolom absensi saat ini: {columns}")
        
        # Tambah kolom jika belum ada
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
        print("🎉 Database migration selesai!")
        
    except Exception as e:
        print(f"❌ Error saat migration: {e}")
        if conn:
            conn.close()
        
def cek_kolom_absensi_pulang():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(absensi)")
    kolom = [row[1] for row in cur.fetchall()]

    if "waktu_pulang" not in kolom:
        cur.execute("ALTER TABLE absensi ADD COLUMN waktu_pulang TEXT")
    if "status_pulang" not in kolom:
        cur.execute("ALTER TABLE absensi ADD COLUMN status_pulang TEXT")
    if "latitude_pulang" not in kolom:
        cur.execute("ALTER TABLE absensi ADD COLUMN latitude_pulang REAL")
    if "longitude_pulang" not in kolom:
        cur.execute("ALTER TABLE absensi ADD COLUMN longitude_pulang REAL")

    conn.commit()
    conn.close()

def hitung_jarak(lat1, lng1, lat2, lng2):
    """Hitung jarak antar koordinat (meter) menggunakan Haversine"""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def dalam_radius(lat_user, lon_user, lat_target, lon_target, radius_meter=100):
    """Cek apakah user ada dalam radius"""
    jarak = hitung_jarak(lat_user, lon_user, lat_target, lon_target)
    return jarak <= radius_meter, jarak

def get_all_siswa():
    """Ambil semua data siswa"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, nama, kelas, jurusan, foto_path, FROM siswa")
    rows = cur.fetchall()
    conn.close()
    return rows

def cari_siswa_dengan_wajah(file_path):
    """Cocokkan wajah dengan data siswa - Versi stabil dan akurat (threshold 0.42)"""
    try:
        print(f"🔍 Memproses file: {file_path}")
        
        # Load dan deteksi wajah
        img_unknown = face_recognition.load_image_file(file_path)
        unknown_encodings = face_recognition.face_encodings(img_unknown)

        print(f"📸 Jumlah wajah terdeteksi: {len(unknown_encodings)}")

        if not unknown_encodings:
            print("❌ Tidak ada wajah terdeteksi pada foto")
            return None

        wajah_absen = unknown_encodings[0]
        print(f"✅ Encoding wajah berhasil dibuat: {len(wajah_absen)} features")

        # Ambil semua data siswa
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, nama, kelas, jurusan, encoding FROM siswa WHERE encoding IS NOT NULL")
        siswa_list = cur.fetchall()
        conn.close()

        print(f"👥 Total siswa terdaftar: {len(siswa_list)}")

        if not siswa_list:
            print("❌ Tidak ada siswa terdaftar dalam database")
            return None

        # ============= PENCARIAN WAJAH TERDEKAT =============
        best_match = None
        best_distance = float("inf")

        for i, (sid, nama, kelas, jurusan, encoding_str) in enumerate(siswa_list):
            try:
                encoding_siswa = ast.literal_eval(encoding_str)
                distance = face_recognition.face_distance([encoding_siswa], wajah_absen)[0]
                print(f"🔄 {i+1}. {nama}: Distance = {distance:.4f}")

                if distance < best_distance:
                    best_distance = distance
                    best_match = {
                        "id": sid,
                        "nama": nama,
                        "kelas": kelas,
                        "jurusan": jurusan,
                        "distance": distance,
                    }

            except Exception as e:
                print(f"❌ Error parsing encoding untuk {nama}: {e}")
                continue

        # ✅ THRESHOLD KETAT
        THRESHOLD = 0.42
        if best_match and best_distance < THRESHOLD:
            print(f"✅ Wajah cocok dengan {best_match['nama']} (distance={best_distance:.4f})")
            return best_match
        else:
            print(f"❌ Tidak ada wajah yang cocok. Jarak terbaik = {best_distance:.4f}")
            return None

    except Exception as e:
        print(f"❌ ERROR di pencocokan wajah: {e}")
        import traceback
        traceback.print_exc()
        return None
# ============= FUNGSI BARU: CEK DUPLIKASI WAJAH SAAT REGISTRASI =============
# ============= FUNGSI CEK DUPLIKASI WAJAH (FIXED) =============
def cek_wajah_sudah_terdaftar(file_path):
    """Cek apakah wajah sudah pernah terdaftar sebelumnya - dengan threshold ketat"""
    try:
        print(f"🔍 Mengecek duplikasi untuk file: {file_path}")
        
        # Load dan deteksi wajah dari foto yang akan didaftarkan
        img_new = face_recognition.load_image_file(file_path)
        new_encodings = face_recognition.face_encodings(img_new)
        
        if not new_encodings:
            print("❌ Tidak ada wajah terdeteksi pada foto")
            return None

        new_face_encoding = new_encodings[0]
        print(f"✅ Encoding wajah baru berhasil dibuat")

        # Ambil semua siswa yang sudah terdaftar (DENGAN NOMOR ABSEN)
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, nama, kelas, jurusan, encoding, nomor_absen FROM siswa WHERE encoding IS NOT NULL")
        siswa_list = cur.fetchall()
        conn.close()

        print(f"👥 Mengecek terhadap {len(siswa_list)} siswa terdaftar")

        # ============= CARI YANG PALING MIRIP =============
        best_match = None
        best_distance = float('inf')

        # Bandingkan dengan setiap siswa yang sudah terdaftar
        for sid, nama, kelas, jurusan, encoding_str, nomor_absen in siswa_list:
            if not encoding_str:
                continue
                
            try:
                existing_encoding = ast.literal_eval(encoding_str)
                
                # Hitung jarak
                distance = face_recognition.face_distance([existing_encoding], new_face_encoding)[0]
                
                print(f"🔄 Cek duplikasi dengan {nama}: Distance={distance:.4f}")
                
                if distance < best_distance:
                    best_distance = distance
                    best_match = {
                        "id": sid,
                        "nama": nama,
                        "kelas": kelas,
                        "jurusan": jurusan,
                        "nomor_absen": nomor_absen,  # TAMBAHKAN NOMOR ABSEN
                        "distance": distance
                    }
                        
            except Exception as e:
                print(f"❌ Error parsing encoding untuk {nama}: {e}")
                continue

        # ============= THRESHOLD DUPLIKASI LEBIH KETAT =============
        DUPLICATE_THRESHOLD = FACE_DUPLICATE_THRESHOLD  # Gunakan konstanta global
        
        if best_match and best_distance < DUPLICATE_THRESHOLD:
            print(f"⚠️ DUPLIKASI TERDETEKSI! Wajah mirip dengan {best_match['nama']} (Distance: {best_distance:.4f})")
            return best_match
        else:
            print(f"✅ Tidak ada duplikasi, wajah baru dapat didaftarkan (Closest distance: {best_distance:.4f})")
            return None

    except Exception as e:
        print(f"❌ Error dalam pengecekan duplikasi: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============= FUNGSI HELPER UNTUK NOMOR ABSEN (HARUS DI LUAR!) =============
def generate_nomor_absen(kelas, jurusan):
    """
    Generate nomor absen otomatis berdasarkan kelas dan jurusan
    Format: [KELAS]-[JURUSAN]-[NOMOR_URUT]
    Contoh: X-SIJA1-001, XI-DKV2-015
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        # Cari nomor terakhir untuk kelas-jurusan ini
        prefix = f"{kelas}-{jurusan}"
        cur.execute("""
            SELECT nomor_absen FROM siswa 
            WHERE nomor_absen LIKE ? 
            ORDER BY nomor_absen DESC 
            LIMIT 1
        """, (f"{prefix}-%",))
        
        last = cur.fetchone()
        conn.close()
        
        if last:
            # Ambil nomor urut terakhir dan tambah 1
            last_num = int(last[0].split('-')[-1])
            new_num = last_num + 1
        else:
            # Ini siswa pertama di kelas-jurusan ini
            new_num = 1
        
        nomor_absen = f"{prefix}-{new_num:03d}"
        print(f"📝 Generated nomor absen: {nomor_absen}")
        return nomor_absen
        
    except Exception as e:
        print(f"❌ Error generating nomor absen: {e}")
        # Fallback: gunakan timestamp
        import time
        return f"{kelas}-{jurusan}-{int(time.time())}"
    

# ============= ROUTES LOGIN ADMIN =============
@app.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin_login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        
        if not username or not password:
            flash("Username dan password harus diisi!", "error")
            return render_template("admin/login.html")
        
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash FROM admin WHERE username = ?", (username,))
        admin = cur.fetchone()
        conn.close()
        
        if admin and check_password_hash(admin[2], password):
            session['admin_logged_in'] = True
            session['admin_id'] = admin[0]
            session['admin_username'] = admin[1]
            flash("Login berhasil! Selamat datang.", "success")
            return redirect(url_for("admin_index"))
        else:
            flash("Username atau password salah!", "error")
    
    return render_template("admin/login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Anda telah logout.", "info")
    return redirect(url_for("admin_login"))

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    """Landing page dengan 2 pilihan utama"""
    return render_template("user/index.html")

# Route reset db /tabel
@app.route("/reset_db")
@login_required
def reset_db():
    # Hapus file database lama
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    # Buat ulang tabel & admin default
    buat_tabel()
    buat_admin_default()

    flash("✅ Database berhasil direset (semua data siswa & absensi terhapus).", "success")
    return redirect(url_for("admin_index"))

# -------- USER (Tidak perlu login) --------
@app.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register_user():
    if request.method == "POST":
        nama = request.form.get("nama")
        kelas = request.form.get("kelas")
        jurusan = request.form.get("jurusan")

        if not nama or not kelas or not jurusan:
            flash("Semua field wajib diisi!", "error")
            return redirect(url_for("register_user"))

        # Simpan data ke session untuk digunakan di potret
        session['temp_nama'] = nama
        session['temp_kelas'] = kelas
        session['temp_jurusan'] = jurusan

        flash("Data berhasil disimpan! Silakan lanjut ambil foto.", "success")
        return redirect(url_for("potret_user"))

    return render_template("user/register.html")

# ============= PERBAIKAN ROUTE POTRET_USER - DENGAN VALIDASI DUPLIKASI =============
@app.route("/potret", methods=["GET", "POST"])
def potret_user():
    # Cek apakah ada data temp di session
    if 'temp_nama' not in session:
        flash("Data registrasi tidak ditemukan! Silakan isi form registrasi terlebih dahulu.", "error")
        return redirect(url_for("register_user"))
    
    # Clear flash messages lama saat GET request
    if request.method == "GET":
        session.pop('_flashes', None)
    
    siswa = {
        "nama": session.get('temp_nama'),
        "kelas": session.get('temp_kelas'),
        "jurusan": session.get('temp_jurusan')
    }

    if request.method == "POST":
        file = request.files["foto"]
        
        # ✅ Validasi file sekali saja
        is_valid, error_msg = validate_upload_file(file)
        if not is_valid:
            flash(error_msg, "error")
            return render_template("user/potret.html", siswa=siswa)
        
        # ✅ Simpan foto sementara
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        temp_foto_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4().hex}.jpg")
        file.save(temp_foto_path)

        conn = None  # kita definisikan di luar try agar bisa ditutup di finally
        try:
            # ============= CEK DUPLIKASI WAJAH TERLEBIH DAHULU =============
            siswa_duplikat = cek_wajah_sudah_terdaftar(temp_foto_path)
            
            if siswa_duplikat:
                os.remove(temp_foto_path)
                session.pop('temp_nama', None)
                session.pop('temp_kelas', None)
                session.pop('temp_jurusan', None)
                session.pop('_flashes', None)
                flash(f"⚠️ Wajah Anda sudah terdaftar atas nama '{siswa_duplikat['nama']}' (Nomor Absen: {siswa_duplikat.get('nomor_absen', 'N/A')}) dari kelas {siswa_duplikat['kelas']} {siswa_duplikat['jurusan']}. Tidak dapat mendaftar ulang!", "error")
                return redirect(url_for("absen_harian"))

            # ============= PROSES ENCODING =============
            img = face_recognition.load_image_file(temp_foto_path)
            encodings = face_recognition.face_encodings(img)

            if not encodings:
                os.remove(temp_foto_path)
                flash("Wajah tidak terdeteksi! Pastikan foto jelas dan menghadap kamera.", "error")
                return render_template("user/potret.html", siswa=siswa)

            if len(encodings) > 1:
                os.remove(temp_foto_path)
                flash("Foto berisi lebih dari 1 wajah! Gunakan foto dengan 1 wajah saja.", "error")
                return render_template("user/potret.html", siswa=siswa)

            encoding = encodings[0].tolist()

            # ============= GENERATE NOMOR ABSEN OTOMATIS =============
            nomor_absen = generate_nomor_absen(siswa['kelas'], siswa['jurusan'])
            print(f"✅ Nomor absen untuk {siswa['nama']}: {nomor_absen}")

            # Pindahkan file ke folder faces dengan nama final
            os.makedirs(FACES_DIR, exist_ok=True)
            final_foto_path = os.path.join(FACES_DIR, f"{uuid.uuid4().hex}.jpg")
            os.rename(temp_foto_path, final_foto_path)

            filename = os.path.basename(final_foto_path)

            # ✅ Simpan ke database (dengan timeout dan thread-safe)
            conn = sqlite3.connect(DB_NAME, timeout=10, check_same_thread=False)
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO siswa (nama, kelas, jurusan, wajah_file, encoding, nomor_absen)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
            siswa['nama'],
            siswa['kelas'],
            siswa['jurusan'],
            filename,   
            str(encoding),
            nomor_absen
            ))

            conn.commit()

            # ✅ Hapus session temporary setelah berhasil
            session.pop('temp_nama', None)
            session.pop('temp_kelas', None)
            session.pop('temp_jurusan', None)
            session.pop('_flashes', None)

            flash(f"🎉 Registrasi berhasil! {siswa['nama']} (Nomor Absen: {nomor_absen}) sekarang bisa melakukan absensi.", "success")
            return redirect(url_for("absen_harian"))

        except Exception as e:
            if os.path.exists(temp_foto_path):
                os.remove(temp_foto_path)
            flash(f"Error memproses foto: {str(e)}", "error")
            return render_template("user/potret.html", siswa=siswa)
        
        finally:
            # ✅ Pastikan koneksi selalu ditutup
            if conn:
                conn.close()

    return render_template("user/potret.html", siswa=siswa)

@app.route("/absen", methods=["POST"])
@monitor_performance
@limiter.limit("10 per minute")
def absen():
    """Proses absensi siswa (bisa mode normal / test)"""
    try:
        file = request.files["foto"]
        lat = float(request.form["lat"])
        lng = float(request.form["lng"])

        filename = f"{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)
        
        print(f"\n{'='*50}")
        print(f"📸 PROSES ABSENSI DIMULAI")
        print(f"📁 File: {filename}")
        print(f"📍 Lokasi Asli Device: {lat}, {lng}")
        print(f"{'='*50}\n")

        # Ambil area absensi dari DB
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
        row = cur.fetchone()
        conn.close()

        school_lat, school_lng, radius = row
        jarak = hitung_jarak(lat, lng, school_lat, school_lng)
        
        print(f"📏 Jarak dari sekolah: {jarak:.2f} meter")
        print(f"📏 Radius yang diizinkan: {radius} meter")

        # ======================
        # ⚙️ MODE TEST
        # True  = Abaikan radius & jam (bisa absen dari mana saja)
        # False = Aktifkan validasi normal
        # ======================
        TEST_MODE = False

        # 🚫 Validasi lokasi (bisa dilewati kalau TEST_MODE aktif)
        if not TEST_MODE:
            if jarak > radius:
                if os.path.exists(filepath):
                    os.remove(filepath)
                print(f"❌ ABSENSI DITOLAK: Lokasi di luar area ({jarak:.0f}m > {radius}m)\n")
                return jsonify({
                    "success": False, 
                    "message": f"❌ Absensi gagal! Anda berada di luar area absensi.\n\n"
                              f"📍 Jarak Anda: {jarak:.0f} meter dari sekolah\n"
                              f"📍 Radius maksimal: {radius} meter\n\n"
                              f"Silakan dekati area sekolah untuk melakukan absensi."
                })
        else:
            print(f"⚙️ TEST MODE AKTIF: Validasi jarak dilewati (jarak {jarak:.2f}m)")
            # ✅ Override lokasi agar marker di peta tetap di area sekolah
            lat = school_lat
            lng = school_lng
            print(f"📍 Lokasi diset ke titik sekolah: {lat}, {lng}")

        # PENCOCOKAN WAJAH
        print(f"\n🔍 Memulai pencocokan wajah...")
        siswa = cari_siswa_dengan_wajah(filepath)

        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"🗑️ File temporary dihapus")

        if not siswa:
            print(f"\n❌ ABSENSI GAGAL: Wajah tidak dikenali\n")
            return jsonify({
                "success": False, 
                "message": "❌ Wajah tidak dikenali! Pastikan Anda sudah terdaftar dan foto jelas."
            })

        print(f"\n✅ Wajah dikenali: {siswa['nama']}")
        print(f"📊 Confidence: {1 - siswa['distance']:.2%}")

        # Waktu lokal WIB
        waktu_lokal = datetime.utcnow() + timedelta(hours=7)
        tanggal_hari_ini = waktu_lokal.date()
        jam_sekarang = waktu_lokal.time()

        jam_mulai_masuk = datetime.strptime("06:00", "%H:%M").time()
        jam_akhir_masuk = datetime.strptime("07:30", "%H:%M").time()

        # 🚫 Validasi jam masuk (bisa dilewati kalau TEST_MODE aktif)
        if not TEST_MODE:
            if jam_sekarang < jam_mulai_masuk:
                print(f"⏰ Belum waktunya absen masuk")
                return jsonify({
                    "success": False,
                    "message": f"⏰ Absen masuk hanya bisa dilakukan mulai jam 06:00 WIB.\n\n"
                              f"Sekarang jam {waktu_lokal.strftime('%H:%M')} WIB.\n"
                              f"Silakan kembali saat waktu absensi."
                })
        else:
            print(f"⚙️ TEST MODE AKTIF: Validasi jam dilewati ({waktu_lokal.strftime('%H:%M')})")

        # Tentukan status berdasarkan waktu
        if jam_sekarang > jam_akhir_masuk:
            status = "TERLAMBAT"
            print(f"⏰ Status waktu: TERLAMBAT")
        else:
            status = "HADIR"
            print(f"⏰ Status waktu: TEPAT WAKTU")

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        # Cek apakah sudah absen hari ini
        cur.execute("""
            SELECT id FROM absensi
            WHERE siswa_id = ? AND DATE(waktu) = ?
        """, (siswa["id"], tanggal_hari_ini))
        sudah_absen = cur.fetchone()

        if sudah_absen:
            conn.close()
            print(f"⚠️ Siswa sudah absen hari ini")
            return jsonify({
                "success": False, 
                "message": f"⚠️ {siswa['nama']} sudah melakukan absensi masuk hari ini!\n\nSilakan absen besok atau lakukan absensi pulang saat waktunya."
            })

        # Simpan absensi baru
        cur.execute("""
            INSERT INTO absensi (siswa_id, nama, kelas, jurusan, latitude, longitude, status, waktu) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (siswa["id"], siswa["nama"], siswa["kelas"], siswa["jurusan"], lat, lng, status, waktu_lokal))
        conn.commit()
        conn.close()
        
        print(f"\n🎉 ABSENSI BERHASIL DISIMPAN")
        print(f"{'='*50}\n")

        session['siswa_id'] = siswa['id']
        session['siswa_nama'] = siswa['nama']
        session['siswa_kelas'] = siswa['kelas']
        session['siswa_jurusan'] = siswa['jurusan']

        return jsonify({
            "success": True,
            "redirect": url_for("absensi_user"),
            "nama": siswa["nama"],
            "kelas": siswa["kelas"],
            "jurusan": siswa["jurusan"],
            "status": status
        })

    except Exception as e:
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({"success": False, "message": f"❌ Terjadi kesalahan sistem: {str(e)}"})

# # ===========================================
# # ⚙️ KONFIGURASI SISTEM
# # ===========================================
# TEST_MODE = False  # True = mode bebas lokasi & jam | False = mode real (production)
# # ===========================================

# @app.route("/absen", methods=["POST"])
# def absen():
#     """Proses absensi siswa (mode test aktif: bebas lokasi & jam)"""
#     try:
#         global TEST_MODE

#         file = request.files["foto"]
#         lat = float(request.form["lat"])
#         lng = float(request.form["lng"])

#         filename = f"{uuid.uuid4().hex}.jpg"
#         filepath = os.path.join(UPLOAD_DIR, filename)
#         file.save(filepath)

#         print(f"\n{'='*50}")
#         print(f"📸 PROSES ABSENSI DIMULAI")
#         print(f"📁 File: {filename}")
#         print(f"📍 Lokasi: {lat}, {lng}")
#         print(f"🔧 MODE: {'TEST' if TEST_MODE else 'PRODUCTION'}")
#         print(f"{'='*50}\n")

#         # Ambil area absensi dari DB
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
#         row = cur.fetchone()
#         conn.close()

#         school_lat, school_lng, radius = row
#         jarak = hitung_jarak(lat, lng, school_lat, school_lng)

#         print(f"📏 Jarak dari sekolah: {jarak:.2f} meter")
#         print(f"📏 Radius yang diizinkan: {radius} meter")

#         # ==================================================
#         # 🚫 Validasi lokasi
#         # ==================================================
#         if not TEST_MODE:
#             if jarak > radius:
#                 os.remove(filepath)
#                 print(f"❌ ABSENSI DITOLAK: Lokasi di luar area ({jarak:.0f}m > {radius}m)\n")
#                 return jsonify({
#                     "success": False,
#                     "message": f"❌ Absensi gagal! Anda berada di luar area absensi.\n\n"
#                               f"📍 Jarak Anda: {jarak:.0f} meter dari sekolah\n"
#                               f"📍 Radius maksimal: {radius} meter\n\n"
#                               f"Silakan dekati area sekolah untuk melakukan absensi."
#                 })
#         else:
#             print(f"⚙️ TEST MODE AKTIF: Validasi jarak dilewati (jarak {jarak:.2f}m)")

#         # ==================================================
#         # 🔍 Pencocokan wajah
#         # ==================================================
#         print(f"\n🔍 Memulai pencocokan wajah...")
#         siswa = cari_siswa_dengan_wajah(filepath)

#         if os.path.exists(filepath):
#             os.remove(filepath)
#             print(f"🗑️ File temporary dihapus")

#         if not siswa:
#             print(f"\n❌ ABSENSI GAGAL: Wajah tidak dikenali\n")
#             return jsonify({
#                 "success": False,
#                 "message": "❌ Wajah tidak dikenali! Pastikan Anda sudah terdaftar dan foto jelas."
#             })

#         print(f"\n✅ Wajah dikenali: {siswa['nama']}")
#         print(f"📊 Confidence: {1 - siswa['distance']:.2%}")

#         # ==================================================
#         # 🕒 Validasi waktu
#         # ==================================================
#         waktu_lokal = datetime.utcnow() + timedelta(hours=7)
#         tanggal_hari_ini = waktu_lokal.date()
#         jam_sekarang = waktu_lokal.time()

#         jam_mulai_masuk = datetime.strptime("06:00", "%H:%M").time()
#         jam_akhir_masuk = datetime.strptime("07:30", "%H:%M").time()

#         if not TEST_MODE:
#             if jam_sekarang < jam_mulai_masuk:
#                 print(f"⏰ Belum waktunya absen masuk")
#                 return jsonify({
#                     "success": False,
#                     "message": f"⏰ Absen masuk hanya bisa dilakukan mulai jam 06:00 WIB.\n\n"
#                               f"Sekarang jam {waktu_lokal.strftime('%H:%M')} WIB."
#                 })
#         else:
#             print(f"⚙️ TEST MODE AKTIF: Validasi jam dilewati ({waktu_lokal.strftime('%H:%M')})")

#         # Tentukan status waktu
#         if jam_sekarang > jam_akhir_masuk:
#             status = "TERLAMBAT"
#             print(f"⏰ Status waktu: TERLAMBAT")
#         else:
#             status = "HADIR"
#             print(f"⏰ Status waktu: TEPAT WAKTU")

#         # ==================================================
#         # 💾 Simpan ke database
#         # ==================================================
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()

#         cur.execute("""
#             SELECT id FROM absensi
#             WHERE siswa_id = ? AND DATE(waktu) = ?
#         """, (siswa["id"], tanggal_hari_ini))
#         sudah_absen = cur.fetchone()

#         if sudah_absen:
#             conn.close()
#             print(f"⚠️ Siswa sudah absen hari ini")
#             return jsonify({
#                 "success": False,
#                 "message": f"⚠️ {siswa['nama']} sudah melakukan absensi masuk hari ini!"
#             })

#         cur.execute("""
#             INSERT INTO absensi (siswa_id, nama, kelas, jurusan, latitude, longitude, status, waktu)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#         """, (siswa["id"], siswa["nama"], siswa["kelas"], siswa["jurusan"],
#               lat, lng, status, waktu_lokal))
#         conn.commit()
#         conn.close()

#         print(f"\n🎉 ABSENSI BERHASIL DISIMPAN")
#         print(f"{'='*50}\n")

#         session['siswa_id'] = siswa['id']
#         session['siswa_nama'] = siswa['nama']
#         session['siswa_kelas'] = siswa['kelas']
#         session['siswa_jurusan'] = siswa['jurusan']

#         return jsonify({
#             "success": True,
#             "redirect": url_for("absensi_user"),
#             "nama": siswa["nama"],
#             "kelas": siswa["kelas"],
#             "jurusan": siswa["jurusan"],
#             "status": status
#         })

#     except Exception as e:
#         if 'filepath' in locals() and os.path.exists(filepath):
#             os.remove(filepath)

#         print(f"\n❌ ERROR: {e}")
#         import traceback
#         traceback.print_exc()

#         return jsonify({"success": False, "message": f"❌ Terjadi kesalahan sistem: {str(e)}"})

# # # Ini route absen mode test
# @app.route("/absen", methods=["POST"])
# def absen():
#     """Proses absensi siswa (bisa mode normal / test)"""
#     try:
#         file = request.files["foto"]
#         lat = float(request.form["lat"])
#         lng = float(request.form["lng"])

#         filename = f"{uuid.uuid4().hex}.jpg"
#         filepath = os.path.join(UPLOAD_DIR, filename)
#         file.save(filepath)
        
#         print(f"\n{'='*50}")
#         print(f"📸 PROSES ABSENSI DIMULAI")
#         print(f"📁 File: {filename}")
#         print(f"📍 Lokasi: {lat}, {lng}")
#         print(f"{'='*50}\n")

#         # Ambil area absensi dari DB
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
#         row = cur.fetchone()
#         conn.close()

#         school_lat, school_lng, radius = row
#         jarak = hitung_jarak(lat, lng, school_lat, school_lng)
        
#         print(f"📏 Jarak dari sekolah: {jarak:.2f} meter")
#         print(f"📏 Radius yang diizinkan: {radius} meter")

#         # ======================
#         # ⚙️ MODE TEST
#         # True  = Abaikan radius & jam (bisa absen dari mana saja)
#         # False = Aktifkan validasi normal
#         # ======================
#         TEST_MODE = True

#         # 🚫 Validasi lokasi (bisa dilewati kalau TEST_MODE aktif)
#         if not TEST_MODE:
#             if jarak > radius:
#                 if os.path.exists(filepath):
#                     os.remove(filepath)
#                 print(f"❌ ABSENSI DITOLAK: Lokasi di luar area ({jarak:.0f}m > {radius}m)\n")
#                 return jsonify({
#                     "success": False, 
#                     "message": f"❌ Absensi gagal! Anda berada di luar area absensi.\n\n"
#                               f"📍 Jarak Anda: {jarak:.0f} meter dari sekolah\n"
#                               f"📍 Radius maksimal: {radius} meter\n\n"
#                               f"Silakan dekati area sekolah untuk melakukan absensi."
#                 })
#         else:
#             print(f"⚙️ TEST MODE AKTIF: Validasi jarak dilewati (jarak {jarak:.2f}m)")

#         # PENCOCOKAN WAJAH
#         print(f"\n🔍 Memulai pencocokan wajah...")
#         siswa = cari_siswa_dengan_wajah(filepath)

#         if os.path.exists(filepath):
#             os.remove(filepath)
#             print(f"🗑️ File temporary dihapus")

#         if not siswa:
#             print(f"\n❌ ABSENSI GAGAL: Wajah tidak dikenali\n")
#             return jsonify({
#                 "success": False, 
#                 "message": "❌ Wajah tidak dikenali! Pastikan Anda sudah terdaftar dan foto jelas."
#             })

#         print(f"\n✅ Wajah dikenali: {siswa['nama']}")
#         print(f"📊 Confidence: {1 - siswa['distance']:.2%}")

#         # Waktu lokal WIB
#         waktu_lokal = datetime.utcnow() + timedelta(hours=7)
#         tanggal_hari_ini = waktu_lokal.date()
#         jam_sekarang = waktu_lokal.time()

#         jam_mulai_masuk = datetime.strptime("06:00", "%H:%M").time()
#         jam_akhir_masuk = datetime.strptime("07:30", "%H:%M").time()

#         # 🚫 Validasi jam masuk (bisa dilewati kalau TEST_MODE aktif)
#         if not TEST_MODE:
#             if jam_sekarang < jam_mulai_masuk:
#                 print(f"⏰ Belum waktunya absen masuk")
#                 return jsonify({
#                     "success": False,
#                     "message": f"⏰ Absen masuk hanya bisa dilakukan mulai jam 06:00 WIB.\n\n"
#                               f"Sekarang jam {waktu_lokal.strftime('%H:%M')} WIB.\n"
#                               f"Silakan kembali saat waktu absensi."
#                 })
#         else:
#             print(f"⚙️ TEST MODE AKTIF: Validasi jam dilewati ({waktu_lokal.strftime('%H:%M')})")

#         # Tentukan status berdasarkan waktu
#         if jam_sekarang > jam_akhir_masuk:
#             status = "TERLAMBAT"
#             print(f"⏰ Status waktu: TERLAMBAT")
#         else:
#             status = "HADIR"
#             print(f"⏰ Status waktu: TEPAT WAKTU")

#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()

#         # Cek apakah sudah absen hari ini
#         cur.execute("""
#             SELECT id FROM absensi
#             WHERE siswa_id = ? AND DATE(waktu) = ?
#         """, (siswa["id"], tanggal_hari_ini))
#         sudah_absen = cur.fetchone()

#         if sudah_absen:
#             conn.close()
#             print(f"⚠️ Siswa sudah absen hari ini")
#             return jsonify({
#                 "success": False, 
#                 "message": f"⚠️ {siswa['nama']} sudah melakukan absensi masuk hari ini!\n\nSilakan absen besok atau lakukan absensi pulang saat waktunya."
#             })

#         # Simpan absensi baru
#         cur.execute("""
#             INSERT INTO absensi (siswa_id, nama, kelas, jurusan, latitude, longitude, status, waktu) 
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#         """, (siswa["id"], siswa["nama"], siswa["kelas"], siswa["jurusan"], lat, lng, status, waktu_lokal))
#         conn.commit()
#         conn.close()
        
#         print(f"\n🎉 ABSENSI BERHASIL DISIMPAN")
#         print(f"{'='*50}\n")

#         session['siswa_id'] = siswa['id']
#         session['siswa_nama'] = siswa['nama']
#         session['siswa_kelas'] = siswa['kelas']
#         session['siswa_jurusan'] = siswa['jurusan']

#         return jsonify({
#             "success": True,
#             "redirect": url_for("absensi_user"),
#             "nama": siswa["nama"],
#             "kelas": siswa["kelas"],
#             "jurusan": siswa["jurusan"],
#             "status": status
#         })

#     except Exception as e:
#         if 'filepath' in locals() and os.path.exists(filepath):
#             os.remove(filepath)
        
#         print(f"\n❌ ERROR: {e}")
#         import traceback
#         traceback.print_exc()
        
#         return jsonify({"success": False, "message": f"❌ Terjadi kesalahan sistem: {str(e)}"})

# @app.route("/absen", methods=["POST"])
# def absen():
#     """Proses absensi siswa dengan STRICT location validation"""
#     try:
#         file = request.files["foto"]
#         lat = float(request.form["lat"])
#         lng = float(request.form["lng"])

#         filename = f"{uuid.uuid4().hex}.jpg"
#         filepath = os.path.join(UPLOAD_DIR, filename)
#         file.save(filepath)

#         print(f"\n{'=' * 50}")
#         print("📸 PROSES ABSENSI DIMULAI")
#         print(f"📁 File: {filename}")
#         print(f"📍 Lokasi: {lat}, {lng}")
#         print(f"{'=' * 50}\n")

#         # Ambil area absensi dari DB
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
#         row = cur.fetchone()
#         conn.close()

#         school_lat, school_lng, radius = row
#         jarak = hitung_jarak(lat, lng, school_lat, school_lng)

#         print(f"📏 Jarak dari sekolah: {jarak:.2f} meter")
#         print(f"📏 Radius yang diizinkan: {radius} meter")

#         # ============= STRICT VALIDATION: BLOCK JIKA DILUAR AREA =============
#         if jarak > radius:
#             # Hapus file temporary
#             if os.path.exists(filepath):
#                 os.remove(filepath)

#             print(f"❌ ABSENSI DITOLAK: Lokasi di luar area ({jarak:.0f}m > {radius}m)\n")

#             return jsonify({
#                 "success": False,
#                 "message": (
#                     f"❌ Absensi gagal! Anda berada di luar area absensi.\n\n"
#                     f"📍 Jarak Anda: {jarak:.0f} meter dari sekolah\n"
#                     f"📍 Radius maksimal: {radius} meter\n\n"
#                     f"Silakan dekati area sekolah untuk melakukan absensi."
#                 ),
#             })

#         print("✅ Status lokasi: DALAM AREA")

#         # PENCOCOKAN WAJAH
#         print("\n🔍 Memulai pencocokan wajah...")
#         siswa = cari_siswa_dengan_wajah(filepath)

#         # Hapus file temporary
#         if os.path.exists(filepath):
#             os.remove(filepath)
#             print("🗑️ File temporary dihapus")

#         if not siswa:
#             print("\n❌ ABSENSI GAGAL: Wajah tidak dikenali\n")
#             return jsonify({
#                 "success": False,
#                 "message": "❌ Wajah tidak dikenali! Pastikan Anda sudah terdaftar dan foto jelas.",
#             })

#         print(f"\n✅ Wajah dikenali: {siswa['nama']}")
#         print(f"📊 Confidence: {1 - siswa['distance']:.2%}")

#         # Waktu lokal WIB
#         waktu_lokal = datetime.utcnow() + timedelta(hours=7)
#         tanggal_hari_ini = waktu_lokal.date()
#         jam_sekarang = waktu_lokal.time()

#         # ✅ VALIDASI JAM MASUK (06:00 - 07:30 WIB)
#         jam_mulai_masuk = datetime.strptime("06:00", "%H:%M").time()
#         jam_akhir_masuk = datetime.strptime("07:30", "%H:%M").time()

#         if jam_sekarang < jam_mulai_masuk:
#             print("⏰ Belum waktunya absen masuk")
#             return jsonify({
#                 "success": False,
#                 "message": (
#                     f"⏰ Absen masuk hanya bisa dilakukan mulai jam 06:00 WIB.\n\n"
#                     f"Sekarang jam {waktu_lokal.strftime('%H:%M')} WIB.\n"
#                     f"Silakan kembali saat waktu absensi."
#                 ),
#             })

#         # Tentukan status berdasarkan waktu
#         if jam_sekarang > jam_akhir_masuk:
#             status = "TERLAMBAT"
#             print("⏰ Status waktu: TERLAMBAT")
#         else:
#             status = "HADIR"
#             print("⏰ Status waktu: TEPAT WAKTU")

#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()

#         # Cek apakah sudah absen hari ini
#         cur.execute("""
#             SELECT id FROM absensi
#             WHERE siswa_id = ? AND DATE(waktu) = ?
#         """, (siswa["id"], tanggal_hari_ini))
#         sudah_absen = cur.fetchone()

#         if sudah_absen:
#             conn.close()
#             print("⚠️ Siswa sudah absen hari ini")
#             return jsonify({
#                 "success": False,
#                 "message": (
#                     f"⚠️ {siswa['nama']} sudah melakukan absensi masuk hari ini!\n\n"
#                     f"Silakan absen besok atau lakukan absensi pulang saat waktunya."
#                 ),
#             })

#         # Simpan absensi baru
#         cur.execute("""
#             INSERT INTO absensi (siswa_id, nama, kelas, jurusan, latitude, longitude, status, waktu)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#         """, (
#             siswa["id"],
#             siswa["nama"],
#             siswa["kelas"],
#             siswa["jurusan"],
#             lat,
#             lng,
#             status,
#             waktu_lokal,
#         ))

#         conn.commit()
#         conn.close()

#         print("\n🎉 ABSENSI BERHASIL DISIMPAN")
#         print(f"{'=' * 50}\n")

#         session["siswa_id"] = siswa["id"]
#         session["siswa_nama"] = siswa["nama"]
#         session["siswa_kelas"] = siswa["kelas"]
#         session["siswa_jurusan"] = siswa["jurusan"]

#         return jsonify({
#             "success": True,
#             "redirect": url_for("absensi_user"),
#             "nama": siswa["nama"],
#             "kelas": siswa["kelas"],
#             "jurusan": siswa["jurusan"],
#             "status": status,
#         })

#     except Exception as e:
#         # Hapus file jika ada error
#         if "filepath" in locals() and os.path.exists(filepath):
#             os.remove(filepath)

#         print(f"\n❌ ERROR: {e}")
#         import traceback
#         traceback.print_exc()

#         return jsonify({
#             "success": False,
#             "message": f"❌ Terjadi kesalahan sistem: {str(e)}",
#     })
    
@app.route("/absen_harian", methods=["GET", "POST"])
def absen_harian():
    """Halaman absensi harian - GET untuk form, POST untuk proses wajah"""

    if request.method == "GET":
        # Cek apakah sudah ada siswa terdaftar
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM siswa WHERE encoding IS NOT NULL")
        total_siswa_terdaftar = cur.fetchone()[0]
        conn.close()

        if total_siswa_terdaftar == 0:
            flash("Belum ada siswa yang terdaftar! Silakan daftar terlebih dahulu.", "warning")
            return redirect(url_for("register_user"))

        return render_template("user/absen_harian.html")

    # ========== Kalau POST ==========
    file = request.files.get("foto")
    if not file:
        return jsonify({"success": False, "message": "Foto tidak ditemukan."})

    # Simpan foto sementara
    temp_path = os.path.join(UPLOAD_DIR, f"absen_{uuid.uuid4().hex}.jpg")
    file.save(temp_path)

    try:
        # Encode wajah
        img = face_recognition.load_image_file(temp_path)
        encodings = face_recognition.face_encodings(img)
        os.remove(temp_path)

        if not encodings:
            return jsonify({"success": False, "message": "Wajah tidak terdeteksi!"})

        encoding = encodings[0]

        # Bandingkan dengan semua siswa
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, nama, kelas, jurusan, encoding FROM siswa WHERE encoding IS NOT NULL")
        siswa_list = cur.fetchall()
        conn.close()

        cocok = None
        for s in siswa_list:
            db_encoding = np.array(ast.literal_eval(s[4]))
            distance = face_recognition.face_distance([db_encoding], encoding)[0]

            if distance < 0.42:  # threshold
                cocok = {
                    "id": s[0],
                    "nama": s[1],
                    "kelas": s[2],
                    "jurusan": s[3]
                }
                break

        if cocok:
            # Simpan absensi
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("INSERT INTO absensi (siswa_id, waktu) VALUES (?, datetime('now'))", (cocok["id"],))
            conn.commit()
            conn.close()

            return jsonify({
                "success": True,
                "message": f"✅ Absensi berhasil: {cocok['nama']} ({cocok['kelas']} - {cocok['jurusan']})",
                "nama": cocok["nama"],
                "kelas": cocok["kelas"],
                "jurusan": cocok["jurusan"]
            })
        else:
            return jsonify({"success": False, "message": "❌ Wajah tidak dikenali!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Error saat absensi: {str(e)}"})

@app.route("/check_students")
def check_students():
    """API endpoint untuk mengecek jumlah siswa yang sudah terdaftar"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM siswa WHERE encoding IS NOT NULL")
    total_students = cur.fetchone()[0]
    conn.close()
    
    return jsonify({
        "total_students": total_students
    })

@app.route("/check_registered")
def check_registered():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM siswa")
    count = cursor.fetchone()[0]
    conn.close()

    if count > 0:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False})

# Update route /absensi di app.py dengan query ini:
# @app.route("/absensi")
# def absensi_user():
#     """Tabel absensi untuk user - hanya tampilkan absensinya sendiri"""
#     if 'siswa_id' not in session:
#         flash("Silakan lakukan absensi terlebih dahulu untuk melihat data Anda.", "warning")
#         return redirect(url_for("index"))

#     conn = sqlite3.connect(DB_NAME)
#     cur = conn.cursor()

#     # Ambil hanya absensi milik siswa ini
#     cur.execute("""
#         SELECT 
#             a.nama, a.kelas, a.jurusan, 
#             COALESCE(s.nomor_absen, '-') as nomor_absen,
#             a.status, a.waktu,
#             a.status_pulang, a.waktu_pulang
#         FROM absensi a
#         LEFT JOIN siswa s ON a.siswa_id = s.id
#         WHERE a.siswa_id = ?
#         ORDER BY a.waktu DESC
#     """, (session['siswa_id'],))

#     absensi = cur.fetchall()
#     conn.close()

#     return render_template("user/absensi.html", absensi=absensi)
@app.route("/absensi")
def absensi_user():
    """Tabel absensi untuk user - hanya tampilkan absensinya sendiri"""
    if 'siswa_id' not in session:
        flash("Silakan lakukan absensi terlebih dahulu untuk melihat data Anda.", "warning")
        return redirect(url_for("index"))

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # ✅ QUERY LENGKAP dengan bukti_surat (index 9)
    cur.execute("""
        SELECT 
            a.nama, 
            a.kelas, 
            a.jurusan, 
            COALESCE(s.nomor_absen, '-') AS nomor_absen,
            a.status, 
            a.waktu,
            a.alasan_pulang,
            CASE 
                WHEN a.waktu_pulang IS NULL THEN NULL
                ELSE a.status_pulang
            END AS status_pulang,
            a.waktu_pulang,
            a.bukti_surat
        FROM absensi a
        LEFT JOIN siswa s ON a.siswa_id = s.id
        WHERE a.siswa_id = ?
        ORDER BY a.waktu DESC
    """, (session['siswa_id'],))

    absensi = cur.fetchall()
    conn.close()

    return render_template("user/absensi.html", absensi=absensi)
    
@app.route('/user/bukti_surat/<filename>')
def serve_bukti_surat_user(filename):
    """Serve bukti surat file untuk user (tidak perlu login admin)"""
    # User hanya bisa lihat bukti surat mereka sendiri
    if 'siswa_id' not in session:
        flash("Silakan login terlebih dahulu.", "warning")
        return redirect(url_for("index"))
    
    return send_from_directory('bukti_surat', filename)

# Ini route test mode 
# @app.route("/absen_pulang", methods=["POST"])
# def absen_pulang():
#     """Proses absensi pulang (bisa mode test / normal)"""
#     try:
#         file = request.files["foto"]
#         lat = float(request.form["lat"])
#         lng = float(request.form["lng"])

#         alasan_pulang = request.form.get("alasan", "").strip() 

#         filename = f"pulang_{uuid.uuid4().hex}.jpg"
#         filepath = os.path.join(UPLOAD_DIR, filename)
#         file.save(filepath)

#         print(f"\n{'='*50}")
#         print(f"📸 PROSES ABSENSI PULANG DIMULAI")
#         print(f"📁 File: {filename}")
#         print(f"📍 Lokasi: {lat}, {lng}")
#         print(f"{'='*50}\n")

#         # Ambil area absensi dari DB
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
#         row = cur.fetchone()
#         conn.close()

#         school_lat, school_lng, radius = row
#         jarak = hitung_jarak(lat, lng, school_lat, school_lng)
        
#         print(f"📏 Jarak dari sekolah: {jarak:.2f} meter")
#         print(f"📏 Radius yang diizinkan: {radius} meter")

#         # ======================
#         # ⚙️ MODE TEST
#         # True  = Abaikan radius & jam (bisa absen dari mana saja)
#         # False = Aktifkan validasi normal
#         # ======================
#         TEST_MODE = True

#         if not TEST_MODE:
#             if jarak > radius:
#                 if os.path.exists(filepath):
#                     os.remove(filepath)
#                 print(f"❌ ABSENSI PULANG DITOLAK: Lokasi di luar area ({jarak:.0f}m > {radius}m)\n")
#                 return jsonify({
#                     "success": False, 
#                     "message": f"❌ Absensi pulang gagal! Anda berada di luar area absensi.\n\n"
#                               f"📍 Jarak Anda: {jarak:.0f} meter dari sekolah\n"
#                               f"📍 Radius maksimal: {radius} meter\n\n"
#                               f"Silakan dekati area sekolah untuk melakukan absensi pulang."
#                 })
#         else:
#             print(f"⚙️ TEST MODE AKTIF: Validasi jarak dilewati (jarak {jarak:.2f}m)")

#         # Pencocokan wajah
#         print(f"\n🔍 Memulai pencocokan wajah...")
#         siswa = cari_siswa_dengan_wajah(filepath)
#         print("✅ Selesai pencocokan wajah")

#         if os.path.exists(filepath):
#             os.remove(filepath)
#             print(f"🗑️ File temporary dihapus")

#         if not siswa:
#             print(f"\n❌ ABSENSI PULANG GAGAL: Wajah tidak dikenali\n")
#             return jsonify({
#                 "success": False, 
#                 "message": "❌ Wajah tidak dikenali! Pastikan Anda sudah terdaftar."
#             })

#         print(f"\n✅ Wajah dikenali: {siswa['nama']}")

#        # Waktu lokal WIB
#         waktu_lokal = datetime.utcnow() + timedelta(hours=7)
#         print("🕒 Waktu lokal (WIB):", waktu_lokal.strftime("%H:%M:%S"))
#         waktu_lokal = waktu_lokal.replace(hour=14, minute=30, second=0)
#         tanggal_hari_ini = waktu_lokal.date()
#         jam_sekarang = waktu_lokal.time()

#         # Atur jam normal (ubah sesuai kebutuhanmu)
#         jam_pulang_normal_mulai = datetime.strptime("15:00", "%H:%M").time()
#         jam_pulang_normal_akhir = datetime.strptime("16:00", "%H:%M").time()

#         # Mode test tetap pakai 00–20, hanya untuk pengujian
#         if TEST_MODE:
#             jam_pulang_normal_mulai = datetime.strptime("15:00", "%H:%M").time()
#             jam_pulang_normal_akhir = datetime.strptime("16:00", "%H:%M").time()

#         # Tambahkan toleransi 1 menit (biar jam 15:00 tidak dianggap cepat)
#         toleransi = (datetime.combine(datetime.today(), jam_pulang_normal_mulai) - timedelta(minutes=1)).time()

#         # Tentukan status otomatis
#         if jam_sekarang < toleransi:
#             status_pulang = "PULANG CEPAT"
#             memerlukan_alasan = True
#         elif jam_pulang_normal_mulai <= jam_sekarang <= jam_pulang_normal_akhir:
#             status_pulang = "PULANG TEPAT WAKTU"
#             memerlukan_alasan = False
#         else:
#             status_pulang = "PULANG TERLAMBAT"
#             memerlukan_alasan = False

#         # Jika ada alasan dan waktunya < jam normal, pastikan tetap dianggap "PULANG CEPAT"
#         if memerlukan_alasan and alasan_pulang:
#             status_pulang = "PULANG CEPAT"

#         # 🚫 Validasi alasan di backend
#         if memerlukan_alasan and (not alasan_pulang or len(alasan_pulang) < 5):
#             return jsonify({
#                 "success": False,
#                 "message": "📝 Alasan pulang cepat wajib diisi (minimal 5 karakter)."
#             })

#         print("💬 Jam_sekarang:", jam_sekarang)
#         print("💬 Jam_pulang_normal_mulai:", jam_pulang_normal_mulai)
#         print("💬 Jam_pulang_normal_akhir:", jam_pulang_normal_akhir)
#         print("💬 memerlukan_alasan:", memerlukan_alasan)
#         print("💬 status_pulang:", status_pulang)

#         # Cek absensi hari ini
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("""
#             SELECT id, waktu_pulang FROM absensi
#             WHERE siswa_id = ? AND DATE(waktu) = ?
#         """, (siswa["id"], tanggal_hari_ini))
#         absen_hari_ini = cur.fetchone()

#         if not absen_hari_ini:
#             conn.close()
#             return jsonify({
#                 "success": False, 
#                 "message": f"❌ {siswa['nama']} belum melakukan absensi masuk hari ini!"
#             })

#         if absen_hari_ini[1] is not None:
#             conn.close()
#             return jsonify({
#                 "success": False, 
#                 "message": f"⚠️ {siswa['nama']} sudah melakukan absensi pulang hari ini!"
#             })

#         # Simpan hasil absensi pulang
#         cur.execute("""
#         UPDATE absensi 
#         SET waktu_pulang = ?, status_pulang = ?, latitude_pulang = ?, longitude_pulang = ?, alasan_pulang = ?
#         WHERE id = ?
#         """, (waktu_lokal, status_pulang, lat, lng, alasan_pulang or None, absen_hari_ini[0]))
#         conn.commit()
#         conn.close()

#         print(f"\n🎉 ABSENSI PULANG BERHASIL ({status_pulang}) (MODE {'TEST' if TEST_MODE else 'NORMAL'})")
#         print(f"{'='*50}\n")

#         return jsonify({
#             "success": True,
#             "redirect": url_for("absensi_user"),
#             "nama": siswa["nama"],
#             "kelas": siswa["kelas"],
#             "jurusan": siswa["jurusan"],
#             "status": status_pulang,
#             "waktu": waktu_lokal.strftime("%H:%M:%S"),
#             "alasan": alasan_pulang or ""
#         })

#     except Exception as e:
#         if 'filepath' in locals() and os.path.exists(filepath):
#             os.remove(filepath)
        
#         print(f"\n❌ ERROR: {e}")
#         import traceback
#         traceback.print_exc()
        
#         return jsonify({"success": False, "message": f"❌ Terjadi kesalahan: {str(e)}"})
    
# @app.route("/absen_pulang", methods=["POST"])
# def absen_pulang():
#     """Proses absensi pulang (production-ready dengan pulang cepat support)"""
#     try:
#         file = request.files["foto"]
#         lat = float(request.form["lat"])
#         lng = float(request.form["lng"])
#         alasan_pulang = request.form.get("alasan", "").strip()

#         filename = f"pulang_{uuid.uuid4().hex}.jpg"
#         filepath = os.path.join(UPLOAD_DIR, filename)
#         file.save(filepath)

#         print(f"\n{'='*50}")
#         print(f"📸 PROSES ABSENSI PULANG DIMULAI")
#         print(f"📁 File: {filename}")
#         print(f"📍 Lokasi: {lat}, {lng}")
#         print(f"{'='*50}\n")

#         # Ambil area sekolah
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
#         row = cur.fetchone()
#         conn.close()

#         school_lat, school_lng, radius = row
#         jarak = hitung_jarak(lat, lng, school_lat, school_lng)

#         if jarak > radius:
#             if os.path.exists(filepath):
#                 os.remove(filepath)
#             print(f"❌ ABSENSI PULANG DITOLAK: Di luar area {jarak:.2f}m > {radius}m\n")
#             return jsonify({
#                 "success": False,
#                 "message": f"❌ Anda berada di luar area absensi (jarak {jarak:.1f}m dari sekolah)."
#             })

#         print(f"✅ Lokasi valid ({jarak:.2f}m dari sekolah)")

#         # ⚙️ MODE TEST
#         # True  = Abaikan radius & jam (bisa absen dari mana saja)
# #         # False = Aktifkan validasi normal
# #         # ======================
#         TEST_MODE = True

#         # Pencocokan wajah
#         siswa = cari_siswa_dengan_wajah(filepath)
#         if os.path.exists(filepath): os.remove(filepath)

#         if not siswa:
#             return jsonify({"success": False, "message": "❌ Wajah tidak dikenali."})

#         print(f"✅ Wajah dikenali: {siswa['nama']}")

#         waktu_lokal = datetime.utcnow() + timedelta(hours=7)
#         tanggal_hari_ini = waktu_lokal.date()
#         jam_sekarang = waktu_lokal.time()

#         jam_pulang_normal_mulai = datetime.strptime("15:00", "%H:%M").time()
#         jam_pulang_normal_akhir = datetime.strptime("16:00", "%H:%M").time()

#         # Tentukan status
#         if jam_sekarang < jam_pulang_normal_mulai:
#             status_pulang = "PULANG CEPAT"
#             memerlukan_alasan = True
#         elif jam_pulang_normal_mulai <= jam_sekarang <= jam_pulang_normal_akhir:
#             status_pulang = "PULANG TEPAT WAKTU"
#             memerlukan_alasan = False
#         else:
#             status_pulang = "PULANG TERLAMBAT"
#             memerlukan_alasan = False

#         if memerlukan_alasan and (not alasan_pulang or len(alasan_pulang) < 5):
#             return jsonify({
#                 "success": False,
#                 "message": "📝 Alasan pulang cepat wajib diisi (minimal 5 karakter)."
#             })

#         # Cek absensi hari ini
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("""
#             SELECT id, waktu_pulang FROM absensi
#             WHERE siswa_id = ? AND DATE(waktu) = ?
#         """, (siswa["id"], tanggal_hari_ini))
#         absen_hari_ini = cur.fetchone()

#         if not absen_hari_ini:
#             conn.close()
#             return jsonify({
#                 "success": False,
#                 "message": f"❌ {siswa['nama']} belum melakukan absensi masuk hari ini!"
#             })

#         if absen_hari_ini[1] is not None:
#             conn.close()
#             return jsonify({
#                 "success": False,
#                 "message": f"⚠️ {siswa['nama']} sudah absen pulang hari ini!"
#             })

#         # Simpan absensi pulang
#         cur.execute("""
#             UPDATE absensi 
#             SET waktu_pulang = ?, status_pulang = ?, latitude_pulang = ?, longitude_pulang = ?, alasan_pulang = ?
#             WHERE id = ?
#         """, (waktu_lokal, status_pulang, lat, lng, alasan_pulang or None, absen_hari_ini[0]))
#         conn.commit()
#         conn.close()

#         print(f"🎉 ABSENSI PULANG: {status_pulang}")

#         return jsonify({
#             "success": True,
#             "redirect": url_for("absensi_user"),
#             "nama": siswa["nama"],
#             "kelas": siswa["kelas"],
#             "jurusan": siswa["jurusan"],
#             "status": status_pulang,
#             "waktu": waktu_lokal.strftime("%H:%M:%S"),
#             "alasan": alasan_pulang or ""
#         })

#     except Exception as e:
#         if 'filepath' in locals() and os.path.exists(filepath): os.remove(filepath)
#         print(f"❌ ERROR: {e}")
#         import traceback; traceback.print_exc()
#         return jsonify({"success": False, "message": f"❌ Terjadi kesalahan: {str(e)}"})

# @app.route("/absen_pulang", methods=["POST"])
# def absen_pulang():
#     """Proses absensi pulang (mode test aktif + dukung upload bukti surat)"""
#     try:
#         file = request.files["foto"]
#         lat = float(request.form["lat"])
#         lng = float(request.form["lng"])
#         alasan_pulang = request.form.get("alasan", "").strip()

#         # === Ambil file bukti surat (jika ada) ===
#         bukti_surat = request.files.get("bukti_surat")
#         bukti_surat_path = None

#         filename = f"pulang_{uuid.uuid4().hex}.jpg"
#         filepath = os.path.join(UPLOAD_DIR, filename)
#         file.save(filepath)

#         print(f"\n{'='*50}")
#         print("📸 PROSES ABSENSI PULANG DIMULAI")
#         print(f"📁 File: {filename}")
#         print(f"📍 Lokasi: {lat}, {lng}")
#         print(f"{'='*50}\n")

#         # Ambil area absensi dari DB
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
#         row = cur.fetchone()
#         conn.close()

#         school_lat, school_lng, radius = row
#         jarak = hitung_jarak(lat, lng, school_lat, school_lng)
        
#         print(f"📏 Jarak dari sekolah: {jarak:.2f} meter")
#         print(f"📏 Radius yang diizinkan: {radius} meter")

#         # ======================
#         # ⚙️ MODE TEST
#         # ======================
#         TEST_MODE = True

#         if not TEST_MODE:
#             if jarak > radius:
#                 if os.path.exists(filepath):
#                     os.remove(filepath)
#                 return jsonify({
#                     "success": False, 
#                     "message": f"❌ Anda berada di luar area absensi ({jarak:.1f}m > {radius}m)."
#                 })
#         else:
#             print(f"⚙️ TEST MODE AKTIF — validasi jarak dilewati (jarak {jarak:.2f}m)")

#         # 🔍 Pencocokan wajah
#         siswa = cari_siswa_dengan_wajah(filepath)
#         if os.path.exists(filepath):
#             os.remove(filepath)

#         if not siswa:
#             return jsonify({"success": False, "message": "❌ Wajah tidak dikenali."})

#         print(f"✅ Wajah dikenali: {siswa['nama']}")

#         # Waktu lokal WIB
#         waktu_lokal = datetime.utcnow() + timedelta(hours=7)
#         waktu_lokal = waktu_lokal.replace(hour=14, minute=30, second=0)  # simulasi jam 14:30 (test)
#         tanggal_hari_ini = waktu_lokal.date()
#         jam_sekarang = waktu_lokal.time()

#         # Jam aturan
#         jam_pulang_normal_mulai = datetime.strptime("15:00", "%H:%M").time()
#         jam_pulang_normal_akhir = datetime.strptime("16:00", "%H:%M").time()

#         if TEST_MODE:
#             jam_pulang_normal_mulai = datetime.strptime("15:00", "%H:%M").time()
#             jam_pulang_normal_akhir = datetime.strptime("16:00", "%H:%M").time()

#         toleransi = (datetime.combine(datetime.today(), jam_pulang_normal_mulai) - timedelta(minutes=1)).time()

#         # Tentukan status otomatis
#         if jam_sekarang < toleransi:
#             status_pulang = "PULANG CEPAT"
#             memerlukan_alasan = True
#         elif jam_pulang_normal_mulai <= jam_sekarang <= jam_pulang_normal_akhir:
#             status_pulang = "PULANG TEPAT WAKTU"
#             memerlukan_alasan = False
#         else:
#             status_pulang = "PULANG TERLAMBAT"
#             memerlukan_alasan = False

#         # 🚫 Validasi alasan di backend
#         if memerlukan_alasan and (not alasan_pulang or len(alasan_pulang) < 5):
#             return jsonify({
#                 "success": False,
#                 "message": "📝 Alasan pulang cepat wajib diisi (minimal 5 karakter)."
#             })

#         # 🧾 Upload bukti surat untuk PULANG CEPAT
#         if status_pulang == "PULANG CEPAT":
#             if not bukti_surat or bukti_surat.filename == "":
#                 return jsonify({
#                     "success": False,
#                     "message": "📄 Bukti surat izin wajib diupload untuk pulang cepat!"
#                 })

#             os.makedirs("bukti_surat", exist_ok=True)
#             bukti_filename = f"bukti_{siswa['id']}_{uuid.uuid4().hex}.jpg"
#             bukti_surat_path = os.path.join("bukti_surat", bukti_filename)
#             bukti_surat.save(bukti_surat_path)
#             print(f"✅ Bukti surat disimpan: {bukti_filename}")

#         print("💬 Jam_sekarang:", jam_sekarang)
#         print("💬 status_pulang:", status_pulang)
#         print("💬 alasan:", alasan_pulang)
#         print("💬 bukti_surat:", bukti_surat_path or "-")

#         # Simpan hasil absensi pulang
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("""
#             UPDATE absensi 
#             SET waktu_pulang = ?, status_pulang = ?, latitude_pulang = ?, 
#                 longitude_pulang = ?, alasan_pulang = ?, bukti_surat = ?
#             WHERE siswa_id = ? AND DATE(waktu) = ?
#         """, (
#             waktu_lokal, status_pulang, lat, lng, 
#             alasan_pulang or None, 
#             os.path.basename(bukti_surat_path) if bukti_surat_path else None,
#             siswa["id"], tanggal_hari_ini
#         ))
#         conn.commit()
#         conn.close()

#         print(f"\n🎉 ABSENSI PULANG BERHASIL ({status_pulang})")
#         print(f"{'='*50}\n")

#         return jsonify({
#             "success": True,
#             "redirect": url_for("absensi_user"),
#             "nama": siswa["nama"],
#             "kelas": siswa["kelas"],
#             "jurusan": siswa["jurusan"],
#             "status": status_pulang,
#             "waktu": waktu_lokal.strftime("%H:%M:%S"),
#             "alasan": alasan_pulang or "",
#             "bukti_surat": os.path.basename(bukti_surat_path) if bukti_surat_path else ""
#         })

#     except Exception as e:
#         if 'filepath' in locals() and os.path.exists(filepath):
#             os.remove(filepath)
#         if 'bukti_surat_path' in locals() and bukti_surat_path and os.path.exists(bukti_surat_path):
#             os.remove(bukti_surat_path)

#         print(f"\n❌ ERROR: {e}")
#         import traceback; traceback.print_exc()

#         return jsonify({"success": False, "message": f"❌ Terjadi kesalahan: {str(e)}"})

@app.route("/absen_pulang", methods=["POST"])
def absen_pulang():
    """Proses absensi pulang (anti dobel + izin pulang cepat + auto radius fix + mode test)"""
    try:
        # ======================
        # ⚙️ MODE TEST (ubah ke False jika real)
        # ======================
        TEST_MODE = False

        # === Ambil data dari form ===
        file = request.files["foto"]
        lat = float(request.form["lat"])
        lng = float(request.form["lng"])
        alasan_pulang = request.form.get("alasan", "").strip()
        bukti_surat = request.files.get("bukti_surat")

        bukti_surat_path = None
        filename = f"pulang_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)

        print(f"\n{'='*60}")
        print("📸 PROSES ABSENSI PULANG DIMULAI")
        print(f"📁 File: {filename}")
        print(f"📍 Lokasi: {lat}, {lng}")
        print(f"{'='*60}\n")

        # === Ambil area absensi ===
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
        row = cur.fetchone()
        school_lat, school_lng, radius = row

        jarak = hitung_jarak(lat, lng, school_lat, school_lng)
        print(f"📏 Jarak dari sekolah: {jarak:.2f} meter (radius {radius}m)")

        # === Validasi lokasi ===
        if jarak > radius:
            if TEST_MODE:
                print("⚙️ TEST MODE AKTIF — lokasi dikoreksi ke titik sekolah.")
                lat, lng = school_lat, school_lng
            else:
                os.remove(filepath)
                conn.close()
                return jsonify({
                    "success": False,
                    "message": f"❌ Anda berada di luar area absensi ({jarak:.1f}m > {radius}m)."
                })

        # === Cek wajah ===
        siswa = cari_siswa_dengan_wajah(filepath)
        os.remove(filepath)

        if not siswa:
            conn.close()
            return jsonify({"success": False, "message": "❌ Wajah tidak dikenali."})

        print(f"✅ Wajah dikenali: {siswa['nama']}")

        # === Waktu lokal ===
        waktu_lokal = datetime.utcnow() + timedelta(hours=7)
        # waktu_lokal = waktu_lokal.replace(hour=15, minute=30, second=0)  # simulasi jam 15:30 (test)
        tanggal_hari_ini = waktu_lokal.date()
        jam_sekarang = waktu_lokal.time()

        # === Cek apakah sudah absen pulang hari ini ===
        cur.execute("""
            SELECT waktu_pulang FROM absensi 
            WHERE siswa_id = ? AND DATE(waktu) = ?
        """, (siswa["id"], tanggal_hari_ini))
        existing = cur.fetchone()

        if existing and existing[0] is not None:
            conn.close()
            return jsonify({
                "success": False,
                "message": "⚠️ Anda sudah melakukan absensi pulang hari ini."
            })

        # === Batas jam aturan ===
        jam_pulang_mulai = datetime.strptime("15:00", "%H:%M").time()
        jam_pulang_akhir = datetime.strptime("16:00", "%H:%M").time()

        # === Tentukan status absensi pulang ===
        if jam_sekarang < jam_pulang_mulai:
            status_pulang = "PULANG CEPAT"

            # Wajib isi alasan & upload surat
            if not alasan_pulang or len(alasan_pulang) < 5:
                conn.close()
                return jsonify({
                    "success": False,
                    "message": "📝 Alasan pulang cepat wajib diisi (minimal 5 karakter)."
                })
            if not bukti_surat or bukti_surat.filename == "":
                conn.close()
                return jsonify({
                    "success": False,
                    "message": "📄 Bukti surat izin wajib diupload untuk pulang cepat!"
                })

            os.makedirs("bukti_surat", exist_ok=True)
            bukti_filename = f"bukti_{siswa['id']}_{uuid.uuid4().hex}.jpg"
            bukti_surat_path = os.path.join("bukti_surat", bukti_filename)
            bukti_surat.save(bukti_surat_path)
            print(f"✅ Bukti surat disimpan: {bukti_filename}")

        elif jam_pulang_mulai <= jam_sekarang <= jam_pulang_akhir:
            status_pulang = "PULANG TEPAT WAKTU"
        else:
            status_pulang = "PULANG TERLAMBAT"

        print(f"💬 Status pulang: {status_pulang}")

        # === Update database ===
        cur.execute("""
            UPDATE absensi 
            SET waktu_pulang = ?, status_pulang = ?, latitude_pulang = ?, 
                longitude_pulang = ?, alasan_pulang = ?, bukti_surat = ?
            WHERE siswa_id = ? AND DATE(waktu) = ?
        """, (
            waktu_lokal, status_pulang, lat, lng,
            alasan_pulang or None,
            os.path.basename(bukti_surat_path) if bukti_surat_path else None,
            siswa["id"], tanggal_hari_ini
        ))
        conn.commit()
        conn.close()

        print(f"\n🎉 ABSENSI PULANG BERHASIL ({status_pulang})")
        print(f"{'='*60}\n")

        # === Redirect ke tabel absensi ===
        return jsonify({
            "success": True,
            "redirect": url_for("absensi_user"),
            "message": f"✅ Absen pulang berhasil ({status_pulang})",
            "nama": siswa["nama"],
            "kelas": siswa["kelas"],
            "jurusan": siswa["jurusan"],
            "status": status_pulang,
            "waktu": waktu_lokal.strftime("%H:%M:%S"),
            "alasan": alasan_pulang or "",
            "bukti_surat": os.path.basename(bukti_surat_path) if bukti_surat_path else ""
        })

    except Exception as e:
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        if 'bukti_surat_path' in locals() and bukti_surat_path and os.path.exists(bukti_surat_path):
            os.remove(bukti_surat_path)

        print(f"\n❌ ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": f"❌ Terjadi kesalahan: {str(e)}"})


# ini clean code saat nanti di deploy
# @app.route("/absen_pulang", methods=["POST"])
# def absen_pulang():
#     """Proses absensi pulang dengan validasi ketat + upload bukti surat (PRODUCTION READY)"""
#     try:
#         file = request.files["foto"]
#         lat = float(request.form["lat"])
#         lng = float(request.form["lng"])
#         alasan_pulang = request.form.get("alasan", "").strip()
        
#         # ============= BARU: Upload bukti surat jika pulang cepat =============
#         bukti_surat = request.files.get("bukti_surat")
#         bukti_surat_path = None

#         filename = f"pulang_{uuid.uuid4().hex}.jpg"
#         filepath = os.path.join(UPLOAD_DIR, filename)
#         file.save(filepath)

#         print(f"\n{'='*50}")
#         print("🏃 PROSES ABSENSI PULANG DIMULAI")
#         print(f"📍 File: {filename}")
#         print(f"📍 Lokasi: {lat}, {lng}")
#         print(f"{'='*50}\n")

#         # Ambil area sekolah
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
#         row = cur.fetchone()
#         conn.close()

#         school_lat, school_lng, radius = row
#         jarak = hitung_jarak(lat, lng, school_lat, school_lng)

#         print(f"📏 Jarak dari sekolah: {jarak:.2f} meter")
#         print(f"📏 Radius yang diizinkan: {radius} meter")

#         # ============= STRICT VALIDATION: BLOCK JIKA DILUAR AREA =============
#         if jarak > radius:
#             if os.path.exists(filepath):
#                 os.remove(filepath)
#             print(f"❌ ABSENSI PULANG DITOLAK: Di luar area ({jarak:.0f}m > {radius}m)\n")
#             return jsonify({
#                 "success": False,
#                 "message": f"❌ Anda berada di luar area absensi (jarak {jarak:.1f}m dari sekolah)."
#             })

#         print("✅ Status lokasi: DALAM AREA")

#         # Pencocokan wajah
#         siswa = cari_siswa_dengan_wajah(filepath)
#         if os.path.exists(filepath): 
#             os.remove(filepath)

#         if not siswa:
#             return jsonify({"success": False, "message": "❌ Wajah tidak dikenali."})

#         print(f"✅ Wajah dikenali: {siswa['nama']}")

#         # Waktu lokal WIB
#         waktu_lokal = datetime.utcnow() + timedelta(hours=7)
#         # bahan testing waktu ke jam normal yang harusnya absen
#         # print("🕒 Waktu lokal (WIB):", waktu_lokal.strftime("%H:%M:%S"))
#         # waktu_lokal = waktu_lokal.replace(hour=15, minute=30, second=0)
#         tanggal_hari_ini = waktu_lokal.date()
#         jam_sekarang = waktu_lokal.time()

#         # ============= VALIDASI JAM PULANG (15:00 - 16:00) =============
#         jam_mulai_pulang = datetime.strptime("15:00", "%H:%M").time()
#         jam_akhir_pulang = datetime.strptime("16:00", "%H:%M").time()

#         memerlukan_alasan = False
        
#         # ❌ TOLAK jika SETELAH jam 16:00 (4 sore)
#         if jam_sekarang > jam_akhir_pulang:
#             print(f"⏰ DITOLAK: Absen pulang sudah lewat jam 16:00 WIB")
#             return jsonify({
#                 "success": False,
#                 "message": f"❌ Waktu absen pulang sudah lewat!\n\n"
#                           f"⏰ Absen pulang hanya bisa dilakukan antara jam 15:00 - 16:00 WIB.\n"
#                           f"Sekarang jam {waktu_lokal.strftime('%H:%M')} WIB.\n\n"
#                           f"Silakan hubungi guru/admin jika ada masalah."
#             })
        
#         # 📋 PULANG CEPAT (sebelum jam 15:00) - WAJIB ALASAN + BUKTI SURAT
#         elif jam_sekarang < jam_mulai_pulang:
#             status_pulang = "PULANG CEPAT"
#             memerlukan_alasan = True
#             print(f"⚠️ Status: PULANG CEPAT (sebelum jam 15:00)")
            
#             # ❌ Validasi alasan wajib diisi
#             if not alasan_pulang or len(alasan_pulang) < 5:
#                 return jsonify({
#                     "success": False,
#                     "message": "📝 Alasan pulang cepat wajib diisi (minimal 5 karakter)."
#                 })
            
#             # ============= VALIDASI BUKTI SURAT (WAJIB UNTUK PULANG CEPAT) =============
#             if not bukti_surat or bukti_surat.filename == '':
#                 return jsonify({
#                     "success": False,
#                     "message": "📄 Bukti surat izin wajib diupload untuk pulang cepat!\n\n"
#                               "Silakan upload foto surat izin dari orang tua/wali atau surat keterangan resmi."
#                 })
            
#             # Validasi file bukti surat
#             is_valid, error_msg = validate_upload_file(bukti_surat)
#             if not is_valid:
#                 return jsonify({"success": False, "message": f"❌ {error_msg}"})
            
#             # Simpan bukti surat
#             os.makedirs("bukti_surat", exist_ok=True)
#             bukti_filename = f"bukti_{siswa['id']}_{uuid.uuid4().hex}.jpg"
#             bukti_surat_path = os.path.join("bukti_surat", bukti_filename)
#             bukti_surat.save(bukti_surat_path)
#             print(f"✅ Bukti surat disimpan: {bukti_filename}")
        
#         # ✅ PULANG TEPAT WAKTU (15:00 - 16:00)
#         else:
#             status_pulang = "PULANG TEPAT WAKTU"
#             memerlukan_alasan = False
#             print(f"✅ Status: PULANG TEPAT WAKTU")

#         # Cek absensi hari ini
#         conn = sqlite3.connect(DB_NAME)
#         cur = conn.cursor()
#         cur.execute("""
#             SELECT id, waktu_pulang FROM absensi
#             WHERE siswa_id = ? AND DATE(waktu) = ?
#         """, (siswa["id"], tanggal_hari_ini))
#         absen_hari_ini = cur.fetchone()

#         if not absen_hari_ini:
#             conn.close()
#             return jsonify({
#                 "success": False,
#                 "message": f"❌ {siswa['nama']} belum melakukan absensi masuk hari ini!\n\n"
#                           f"Silakan lakukan absensi masuk terlebih dahulu."
#             })

#         if absen_hari_ini[1] is not None:
#             conn.close()
#             # Hapus bukti surat jika ada
#             if bukti_surat_path and os.path.exists(bukti_surat_path):
#                 os.remove(bukti_surat_path)
#             return jsonify({
#                 "success": False,
#                 "message": f"⚠️ {siswa['nama']} sudah melakukan absensi pulang hari ini!"
#             })

#         # ============= SIMPAN ABSENSI PULANG =============
#         cur.execute("""
#             UPDATE absensi 
#             SET waktu_pulang = ?, status_pulang = ?, latitude_pulang = ?, longitude_pulang = ?, 
#                 alasan_pulang = ?, bukti_surat = ?
#             WHERE id = ?
#         """, (
#             waktu_lokal, 
#             status_pulang, 
#             lat, 
#             lng, 
#             alasan_pulang if memerlukan_alasan else None,
#             os.path.basename(bukti_surat_path) if bukti_surat_path else None,
#             absen_hari_ini[0]
#         ))

#         conn.commit()
#         conn.close()

#         print(f"\n🎉 ABSENSI PULANG BERHASIL: {status_pulang}")
#         print(f"{'='*50}\n")

#         return jsonify({
#             "success": True,
#             "redirect": url_for("absensi_user"),
#             "nama": siswa["nama"],
#             "kelas": siswa["kelas"],
#             "jurusan": siswa["jurusan"],
#             "status": status_pulang,
#             "waktu": waktu_lokal.strftime("%H:%M:%S"),
#             "alasan": alasan_pulang if memerlukan_alasan else ""
#         })

#     except Exception as e:
#         # Cleanup jika error
#         if 'filepath' in locals() and os.path.exists(filepath):
#             os.remove(filepath)
#         if 'bukti_surat_path' in locals() and bukti_surat_path and os.path.exists(bukti_surat_path):
#             os.remove(bukti_surat_path)
        
#         print(f"\n❌ ERROR: {e}")
#         import traceback
#         traceback.print_exc()
        
#         return jsonify({"success": False, "message": f"❌ Terjadi kesalahan: {str(e)}"})
    
@app.route("/absen_pulang_harian", methods=["GET"])
def absen_pulang_harian():
    """Halaman absensi pulang — bisa diakses kapan saja"""

    # Waktu lokal WIB (tetap simpan untuk keperluan log)
    waktu_lokal = datetime.utcnow() + timedelta(hours=7)
    jam_sekarang = waktu_lokal.strftime("%H:%M")

    print(f"🕒 Halaman absen pulang diakses pada {jam_sekarang} WIB")

    # Cek apakah sudah ada siswa terdaftar
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM siswa WHERE encoding IS NOT NULL")
    total_siswa_terdaftar = cur.fetchone()[0]
    conn.close()

    if total_siswa_terdaftar == 0:
        flash("Belum ada siswa yang terdaftar! Silakan daftar terlebih dahulu.", "warning")
        return redirect(url_for("register_user"))

    return render_template("user/absen_pulang.html")

# -------- ADMIN (Perlu login) --------
@app.route("/admin")
@login_required
def admin_index():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # total siswa
    cur.execute("SELECT COUNT(*) FROM siswa")
    total_siswa = cur.fetchone()[0]

    # total absensi
    cur.execute("SELECT COUNT(*) FROM absensi")
    total_absensi = cur.fetchone()[0]

    # absensi hari ini
    today = datetime.utcnow() + timedelta(hours=7)  # WIB
    today_str = today.date()
    cur.execute("SELECT COUNT(*) FROM absensi WHERE DATE(waktu) = ?", (today_str,))
    absensi_hari_ini = cur.fetchone()[0]

    # persentase kehadiran hari ini
    if total_siswa > 0:
        persentase = round((absensi_hari_ini / total_siswa) * 100, 2)
    else:
        persentase = 0

    conn.close()

    return render_template(
        "admin/index.html",
        total_siswa=total_siswa,
        absensi_hari_ini=absensi_hari_ini,
        total_absensi=total_absensi,
        persentase=persentase,
        admin_username=session.get('admin_username')
    )

@app.route("/admin/absensi")
@login_required
def admin_absensi():
    """Tabel absensi untuk admin dengan fitur pencarian"""
    search_query = request.args.get("q", "").strip()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if search_query:
        cur.execute("""
            SELECT a.nama, a.kelas, a.jurusan, a.status, a.waktu, a.latitude, a.longitude,
                   COALESCE(s.nomor_absen, '-') as nomor_absen
            FROM absensi a
            LEFT JOIN siswa s ON a.siswa_id = s.id
            WHERE a.nama LIKE ? OR a.kelas LIKE ? OR a.jurusan LIKE ? OR s.nomor_absen LIKE ?
            ORDER BY a.waktu DESC
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        cur.execute("""
            SELECT a.nama, a.kelas, a.jurusan, a.status, a.waktu, a.latitude, a.longitude,
                   COALESCE(s.nomor_absen, '-') as nomor_absen
            FROM absensi a
            LEFT JOIN siswa s ON a.siswa_id = s.id
            ORDER BY a.waktu DESC
        """)

    rows = cur.fetchall()
    conn.close()

    absensi = [
        {
            "nama": r[0],
            "kelas": r[1],
            "jurusan": r[2],
            "status": r[3],
            "waktu": r[4],
            "lat": r[5],
            "lng": r[6],
            "nomor_absen": r[7]
        }
        for r in rows
    ]

    return render_template(
        "admin/absensi.html",
        absensi=absensi,
        SCHOOL_LAT=SCHOOL_LAT,
        SCHOOL_LNG=SCHOOL_LNG,
        search_query=search_query
    )
    
@app.route("/admin/absen_area")
@login_required
def admin_absen_area():
    return render_template("admin/absen_area.html")

@app.route("/admin/register", methods=["GET", "POST"])
@login_required
def admin_register():
    if request.method == "POST":
        nama = request.form["nama"]
        kelas = request.form["kelas"]
        jurusan = request.form["jurusan"]
        file = request.files["foto"]

         # ✅ VALIDASI FILE
        is_valid, error_msg = validate_upload_file(file)
        if not is_valid:
            flash(error_msg, "error")
            return render_template("admin/register.html")
        

        # Validasi file
        if not file or file.filename == '':
            flash("Foto wajah harus diupload!", "error")
            return render_template("admin/register.html")

        # Simpan foto sementara untuk pengecekan duplikasi
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        temp_foto_path = os.path.join(UPLOAD_DIR, f"admin_temp_{uuid.uuid4().hex}.jpg")
        file.save(temp_foto_path)

        try:
            # ============= CEK DUPLIKASI WAJAH TERLEBIH DAHULU (ADMIN JUGA) =============
            siswa_duplikat = cek_wajah_sudah_terdaftar(temp_foto_path)
            
            if siswa_duplikat:
                os.remove(temp_foto_path)
                flash(f"⚠️ Wajah sudah terdaftar atas nama '{siswa_duplikat['nama']}' (Nomor Absen: {siswa_duplikat.get('nomor_absen', 'N/A')}) dari kelas {siswa_duplikat['kelas']} {siswa_duplikat['jurusan']}. Tidak dapat mendaftar ulang!", "error")
                return render_template("admin/register.html")

            # Encode wajah dengan validasi yang lebih ketat
            img = face_recognition.load_image_file(temp_foto_path)
            encodings = face_recognition.face_encodings(img)
            
            if not encodings:
                os.remove(temp_foto_path)
                flash("Wajah tidak terdeteksi pada foto! Pastikan foto jelas dan menghadap kamera.", "error")
                return render_template("admin/register.html")
            
            if len(encodings) > 1:
                flash("Terdeteksi lebih dari 1 wajah dalam foto! Gunakan foto dengan 1 wajah saja.", "error")
                os.remove(temp_foto_path)
                return render_template("admin/register.html")

            encoding = encodings[0].tolist()

            # ============= GENERATE NOMOR ABSEN OTOMATIS =============
            nomor_absen = generate_nomor_absen(kelas, jurusan)
            print(f"✅ Nomor absen untuk {nama}: {nomor_absen}")

            # Pindahkan file ke folder faces dengan nama final
            os.makedirs(FACES_DIR, exist_ok=True)
            final_foto_path = os.path.join(FACES_DIR, f"admin_{uuid.uuid4().hex}.jpg")
            os.rename(temp_foto_path, final_foto_path)

            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO siswa (nama, kelas, jurusan, foto_path, encoding, nomor_absen) VALUES (?, ?, ?, ?, ?, ?)",
                (nama, kelas, jurusan, final_foto_path, str(encoding), nomor_absen)
            )
            conn.commit()
            conn.close()

            flash(f"✅ Siswa {nama} (Nomor Absen: {nomor_absen}) berhasil didaftarkan!", "success")
            return redirect(url_for("admin_register"))

        except Exception as e:
            if os.path.exists(temp_foto_path):
                os.remove(temp_foto_path)
            flash(f"Error saat memproses foto: {str(e)}", "error")
            return render_template("admin/register.html")

    return render_template("admin/register.html")

@app.route("/admin/set_area", methods=["POST"])
@login_required
def admin_set_area():
    """Update area absensi"""
    data = request.get_json()
    lat, lon, radius = data.get("lat"), data.get("lon"), data.get("radius")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE settings SET latitude=?, longitude=?, radius=? WHERE id=1",
        (lat, lon, radius)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Area absensi berhasil diperbarui!"})

@app.route("/admin/get_area")
@login_required
def admin_get_area():
    """Ambil data area absensi"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
    row = cur.fetchone()
    conn.close()

    if row:
        return jsonify({"lat": row[0], "lon": row[1], "radius": row[2]})
    else:
        return jsonify({"lat": SCHOOL_LAT, "lon": SCHOOL_LNG, "radius": RADIUS})

# clean code sebelumnya
# # Update route /admin/absensi_map di app.py
# @app.route('/admin/absensi_map')
# @login_required
# def admin_absensi_map():
#     search_query = request.args.get('q', '').strip()
#     date_filter = request.args.get('date', '').strip()

#     conn = sqlite3.connect(DB_NAME)
#     cur = conn.cursor()

#     # Tanggal default (hari ini)
#     if not date_filter:
#         date_filter = (datetime.utcnow() + timedelta(hours=7)).strftime('%Y-%m-%d')

#     # ✅ QUERY dengan alasan_pulang di kedua blok
#     if search_query:
#         cur.execute("""
#             SELECT 
#                 a.nama, a.kelas, a.jurusan, a.status, a.waktu, 
#                 a.latitude, a.longitude,
#                 a.status_pulang, a.waktu_pulang, 
#                 a.latitude_pulang, a.longitude_pulang,
#                 COALESCE(s.nomor_absen, '-') AS nomor_absen,
#                 a.alasan_pulang
#             FROM absensi a
#             LEFT JOIN siswa s ON a.siswa_id = s.id
#             WHERE DATE(a.waktu) = ?
#               AND (
#                   a.nama LIKE ? OR
#                   a.kelas LIKE ? OR
#                   a.jurusan LIKE ? OR
#                   s.nomor_absen LIKE ?
#               )
#             ORDER BY a.waktu DESC
#         """, (date_filter, f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
#     else:
#         cur.execute("""
#             SELECT 
#                 a.nama, a.kelas, a.jurusan, a.status, a.waktu, 
#                 a.latitude, a.longitude,
#                 a.status_pulang, a.waktu_pulang, 
#                 a.latitude_pulang, a.longitude_pulang,
#                 COALESCE(s.nomor_absen, '-') AS nomor_absen,
#                 a.alasan_pulang
#             FROM absensi a
#             LEFT JOIN siswa s ON a.siswa_id = s.id
#             WHERE DATE(a.waktu) = ?
#             ORDER BY a.waktu DESC
#         """, (date_filter,))

#     absensi = cur.fetchall()
#     conn.close()
#     total_absensi = len(absensi)

#     # Format tanggal untuk display (Indonesia)
#     try:
#         date_obj = datetime.strptime(date_filter, '%Y-%m-%d')
#         formatted_date = date_obj.strftime('%d %B %Y')
        
#         # Translate bulan ke Indonesia
#         bulan_id = {
#             'January': 'Januari', 'February': 'Februari', 'March': 'Maret',
#             'April': 'April', 'May': 'Mei', 'June': 'Juni',
#             'July': 'Juli', 'August': 'Agustus', 'September': 'September',
#             'October': 'Oktober', 'November': 'November', 'December': 'Desember'
#         }
#         for eng, ind in bulan_id.items():
#             formatted_date = formatted_date.replace(eng, ind)
#     except:
#         formatted_date = date_filter
    
#     return render_template(
#         'admin/absensi_map.html',
#         absensi=absensi,
#         search_query=search_query,
#         date_filter=date_filter,
#         formatted_date=formatted_date,
#         total_absensi=total_absensi,
#         SCHOOL_LAT=SCHOOL_LAT,
#         SCHOOL_LNG=SCHOOL_LNG,
#         RADIUS=RADIUS
#     )

# GANTI route /admin/absensi_map di app.py dengan ini:

@app.route('/admin/absensi_map')
@login_required
def admin_absensi_map():
    search_query = request.args.get('q', '').strip()
    date_filter = request.args.get('date', '').strip()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Tanggal default (hari ini)
    if not date_filter:
        date_filter = (datetime.utcnow() + timedelta(hours=7)).strftime('%Y-%m-%d')

    # ✅ QUERY LENGKAP dengan bukti_surat (index 13)
    if search_query:
        cur.execute("""
            SELECT 
                a.nama, a.kelas, a.jurusan, a.status, a.waktu, 
                a.latitude, a.longitude,
                a.status_pulang, a.waktu_pulang, 
                a.latitude_pulang, a.longitude_pulang,
                COALESCE(s.nomor_absen, '-') AS nomor_absen,
                a.alasan_pulang,
                a.bukti_surat
            FROM absensi a
            LEFT JOIN siswa s ON a.siswa_id = s.id
            WHERE DATE(a.waktu) = ?
              AND (
                  a.nama LIKE ? OR
                  a.kelas LIKE ? OR
                  a.jurusan LIKE ? OR
                  s.nomor_absen LIKE ?
              )
            ORDER BY a.waktu DESC
        """, (date_filter, f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        cur.execute("""
            SELECT 
                a.nama, a.kelas, a.jurusan, a.status, a.waktu, 
                a.latitude, a.longitude,
                a.status_pulang, a.waktu_pulang, 
                a.latitude_pulang, a.longitude_pulang,
                COALESCE(s.nomor_absen, '-') AS nomor_absen,
                a.alasan_pulang,
                a.bukti_surat
            FROM absensi a
            LEFT JOIN siswa s ON a.siswa_id = s.id
            WHERE DATE(a.waktu) = ?
            ORDER BY a.waktu DESC
        """, (date_filter,))

    absensi = cur.fetchall()
    conn.close()
    total_absensi = len(absensi)

    # Format tanggal untuk display (Indonesia)
    try:
        date_obj = datetime.strptime(date_filter, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d %B %Y')
        
        # Translate bulan ke Indonesia
        bulan_id = {
            'January': 'Januari', 'February': 'Februari', 'March': 'Maret',
            'April': 'April', 'May': 'Mei', 'June': 'Juni',
            'July': 'Juli', 'August': 'Agustus', 'September': 'September',
            'October': 'Oktober', 'November': 'November', 'December': 'Desember'
        }
        for eng, ind in bulan_id.items():
            formatted_date = formatted_date.replace(eng, ind)
    except:
        formatted_date = date_filter
    
    return render_template(
        'admin/absensi_map.html',
        absensi=absensi,
        search_query=search_query,
        date_filter=date_filter,
        formatted_date=formatted_date,
        total_absensi=total_absensi,
        SCHOOL_LAT=SCHOOL_LAT,
        SCHOOL_LNG=SCHOOL_LNG,
        RADIUS=RADIUS
    )

# ============= TAMBAHKAN ROUTE BARU: SERVE BUKTI SURAT =============
@app.route('/bukti_surat/<filename>')
@login_required
def serve_bukti_surat(filename):
    """Serve bukti surat file untuk admin"""
    return send_from_directory('bukti_surat', filename)

@app.route("/admin/kelola_siswa")
@login_required
def admin_kelola_siswa():
    filter_kelas = request.args.get('kelas', '').strip()
    filter_jurusan = request.args.get('jurusan', '').strip().upper()
    search = request.args.get('search', '').strip().lower()  # 🔍 Tambahan
    
    try:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        
        query = "SELECT id, nama, kelas, jurusan, nomor_absen, wajah_file FROM siswa WHERE 1=1"
        params = []
        
        if filter_kelas:
            query += " AND kelas = ?"
            params.append(filter_kelas)
        
        if filter_jurusan:
             query += " AND REPLACE(UPPER(jurusan), ' ', '') = ?"
             params.append(filter_jurusan.upper().replace(' ', ''))
        
        if search:  # 🔍 Filter nama
            query += " AND LOWER(nama) LIKE ?"
            params.append(f"%{search}%")
        
        query += " ORDER BY kelas, jurusan, nomor_absen"
        c.execute(query, params)
        data = c.fetchall()
        
        # Ambil daftar kelas & jurusan seperti sebelumnya ...
        c.execute("SELECT DISTINCT kelas FROM siswa ORDER BY kelas")
        kelas_list = [row[0] for row in c.fetchall() if row[0]]
        
        c.execute("SELECT DISTINCT jurusan FROM siswa ORDER BY jurusan")
        raw_jurusan = [row[0] for row in c.fetchall() if row[0]]
        
        jurusan_list = []
        for j in raw_jurusan:
            j_clean = j.strip().upper().replace(" ", "")
            if j_clean not in jurusan_list:
                jurusan_list.append(j_clean)
        
        tambahan_jurusan = ["PB3", "DKV3"]
        for j in tambahan_jurusan:
            if j.upper() not in jurusan_list:
                jurusan_list.append(j.upper())
        
        jurusan_list = sorted(jurusan_list)
        
        conn.close()
        total_siswa = len(data)
        
        return render_template(
            "admin/kelola_siswa.html",
            data=data,
            kelas_list=kelas_list,
            jurusan_list=jurusan_list,
            filter_kelas=filter_kelas,
            filter_jurusan=filter_jurusan,
            total_siswa=total_siswa,
            search=search  # 🔍 Kirim ke template
        )
    except Exception as e:
        print("❌ Error kelola_siswa:", e)
        flash("Gagal memuat data siswa", "error")
        return redirect(url_for("admin_index"))

@app.route("/hapus_siswa/<int:id>")
def hapus_siswa(id):
    try:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("DELETE FROM siswa WHERE id=?", (id,))
        conn.commit()
        conn.close()
        flash("✅ Data siswa berhasil dihapus", "success")
    except Exception as e:
        print("❌ Error hapus_siswa:", e)
        flash("Gagal menghapus data siswa", "error")
    return redirect(url_for("admin_kelola_siswa"))

@app.route("/edit_siswa/<int:id>", methods=["GET", "POST"])
def edit_siswa(id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        nama = request.form["nama"]
        kelas = request.form["kelas"]
        jurusan = request.form["jurusan"]
        nomor_absen = request.form["nomor_absen"]

        c.execute("""
            UPDATE siswa 
            SET nama=?, kelas=?, jurusan=?, nomor_absen=?
            WHERE id=?
        """, (nama, kelas, jurusan, nomor_absen, id))
        conn.commit()
        conn.close()
        flash("✅ Data siswa berhasil diperbarui", "success")
        return redirect(url_for("admin_kelola_siswa"))

    c.execute("SELECT id, nama, kelas, jurusan, nomor_absen FROM siswa WHERE id=?", (id,))
    siswa = c.fetchone()
    conn.close()

    if not siswa:
        flash("❌ Data siswa tidak ditemukan", "error")
        return redirect(url_for("admin_kelola_siswa"))

    return render_template("admin/edit_siswa.html", siswa=siswa)

@app.route("/admin/analytics")
@login_required
def admin_analytics():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # ==================== STATISTIK DASAR ====================
    cur.execute("SELECT COUNT(*) FROM siswa")
    total_siswa = cur.fetchone()[0]
    
    today = (datetime.utcnow() + timedelta(hours=7)).date()

    cur.execute("SELECT COUNT(*) FROM absensi WHERE DATE(waktu) = ?", (today,))
    absensi_hari_ini = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM siswa 
        WHERE id NOT IN (
            SELECT DISTINCT siswa_id FROM absensi WHERE DATE(waktu) = ?
        )
    """, (today,))
    belum_absen = cur.fetchone()[0]

    # ==================== TREND 30 HARI ====================
    cur.execute("""
        SELECT DATE(waktu) as date, COUNT(*) as count
        FROM absensi
        WHERE waktu >= DATE('now', '-30 days')
        GROUP BY DATE(waktu)
        ORDER BY date
    """)
    trend = [{"date": r[0], "count": r[1]} for r in cur.fetchall()]

    # ==================== STATS PER KELAS (MENAMPILKAN SEMUA) ====================
    cur.execute("SELECT DISTINCT kelas FROM siswa ORDER BY kelas")
    all_kelas = [r[0] for r in cur.fetchall()]

    class_stats = []
    for kelas in all_kelas:
        cur.execute("SELECT COUNT(*) FROM siswa WHERE kelas = ?", (kelas,))
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT a.siswa_id)
            FROM absensi a
            JOIN siswa s ON a.siswa_id = s.id
            WHERE s.kelas = ? AND DATE(a.waktu) = ?
        """, (kelas, today))
        hadir = cur.fetchone()[0] or 0

        alpha = total - hadir
        percentage = round((hadir / total * 100), 1) if total > 0 else 0

        class_stats.append({
            "kelas": kelas,
            "total": total,
            "hadir": hadir,
            "alpha": alpha,
            "percentage": percentage
        })

    # ==================== STATS PER JURUSAN (MENAMPILKAN SEMUA) ====================
    cur.execute("SELECT DISTINCT jurusan FROM siswa ORDER BY jurusan")
    all_jurusan = [r[0] for r in cur.fetchall()]

    jurusan_stats = []
    for jurusan in all_jurusan:
        cur.execute("SELECT COUNT(*) FROM siswa WHERE jurusan = ?", (jurusan,))
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT a.siswa_id)
            FROM absensi a
            JOIN siswa s ON a.siswa_id = s.id
            WHERE s.jurusan = ? AND DATE(a.waktu) = ?
        """, (jurusan, today))
        hadir = cur.fetchone()[0] or 0

        alpha = total - hadir
        percentage = round((hadir / total * 100), 1) if total > 0 else 0

        jurusan_stats.append({
            "jurusan": jurusan,
            "total": total,
            "hadir": hadir,
            "alpha": alpha,
            "percentage": percentage
        })

    # ==================== PEAK HOURS ====================
    cur.execute("""
        SELECT strftime('%H:00', waktu) as hour, COUNT(*) as count
        FROM absensi
        WHERE DATE(waktu) = ?
        GROUP BY hour
        ORDER BY hour
    """, (today,))
    peak_hours = [{"hour": r[0], "count": r[1]} for r in cur.fetchall()]

    # ==================== TOP 10 SISWA TERAJIN ====================
    cur.execute("""
        SELECT s.nama, s.kelas, s.jurusan, s.nomor_absen,
               COUNT(*) as total_hadir,
               SUM(CASE WHEN a.status = 'HADIR' THEN 1 ELSE 0 END) as tepat_waktu,
               SUM(CASE WHEN a.status = 'TERLAMBAT' THEN 1 ELSE 0 END) as terlambat
        FROM absensi a
        JOIN siswa s ON a.siswa_id = s.id
        WHERE a.waktu >= DATE('now', '-30 days')
        GROUP BY s.id
        ORDER BY total_hadir DESC, tepat_waktu DESC
        LIMIT 10
    """)
    top_students = [{
        "nama": r[0],
        "kelas": r[1],
        "jurusan": r[2],
        "nomor_absen": r[3],
        "total_hadir": r[4],
        "tepat_waktu": r[5],
        "terlambat": r[6]
    } for r in cur.fetchall()]

    # ==================== SISWA PALING SERING TERLAMBAT ====================
    cur.execute("""
        SELECT s.nama, s.kelas, s.jurusan, s.nomor_absen,
               COUNT(*) as total_terlambat
        FROM absensi a
        JOIN siswa s ON a.siswa_id = s.id
        WHERE a.status = 'TERLAMBAT' AND a.waktu >= DATE('now', '-30 days')
        GROUP BY s.id
        ORDER BY total_terlambat DESC
        LIMIT 10
    """)
    most_late = [{
        "nama": r[0],
        "kelas": r[1],
        "jurusan": r[2],
        "nomor_absen": r[3],
        "total_terlambat": r[4]
    } for r in cur.fetchall()]

    # ==================== SISWA BELUM ABSEN HARI INI ====================
    cur.execute("""
        SELECT s.nama, s.kelas, s.jurusan, s.nomor_absen
        FROM siswa s
        WHERE s.id NOT IN (
            SELECT DISTINCT siswa_id FROM absensi WHERE DATE(waktu) = ?
        )
        ORDER BY s.kelas, s.jurusan, s.nama
    """, (today,))
    absent_today = [{
        "nama": r[0],
        "kelas": r[1],
        "jurusan": r[2],
        "nomor_absen": r[3]
    } for r in cur.fetchall()]

    conn.close()

    # ==================== FINAL DATA ====================
    stats = {
        "total_siswa": total_siswa,
        "absensi_hari_ini": absensi_hari_ini,
        "belum_absen": belum_absen,
        "persentase_hari_ini": round((absensi_hari_ini / total_siswa * 100), 1) if total_siswa > 0 else 0,
        "absensi_minggu_ini": 0  # TODO: bisa dikembangkan nanti
    }

    return render_template(
        "admin/analytics.html",
        stats=stats,
        trend=trend,
        class_stats=class_stats,
        jurusan_stats=jurusan_stats,
        peak_hours=peak_hours,
        top_students=top_students,
        most_late=most_late,
        absent_today=absent_today,
        weekly_comp=None
    )

@app.route("/admin/export/excel")
@login_required
def export_excel():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("""
        SELECT nama, kelas, jurusan, status, waktu, 
               status_pulang, waktu_pulang 
        FROM absensi
    """, conn)
    conn.close()

    # Rename kolom agar lebih jelas
    df.columns = ['Nama', 'Kelas', 'Jurusan', 'Status Masuk', 'Waktu Masuk', 'Status Pulang', 'Waktu Pulang']

    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="laporan_absensi.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# Replace fungsi export_pdf di app.py
@app.route("/admin/export/pdf")
@login_required
def export_pdf():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT nama, kelas, jurusan, status, waktu, 
               status_pulang, waktu_pulang 
        FROM absensi 
        ORDER BY waktu DESC
    """)
    data = cur.fetchall()
    conn.close()

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    small_style = ParagraphStyle(
        'small',
        parent=styles['Normal'],
        fontSize=7,
        leading=9,
        alignment=1
    )

    elements.append(Paragraph("Laporan Absensi (Masuk & Pulang)", styles['Title']))

    table_data = [
        [Paragraph("Nama", small_style),
         Paragraph("Kelas", small_style),
         Paragraph("Jurusan", small_style),
         Paragraph("Status Masuk", small_style),
         Paragraph("Waktu Masuk", small_style),
         Paragraph("Status Pulang", small_style),
         Paragraph("Waktu Pulang", small_style)]
    ]

    for row in data:
        nama, kelas, jurusan, status, waktu, status_pulang, waktu_pulang = row
        waktu_fmt = str(waktu).split(".")[0] if waktu else "-"
        waktu_pulang_fmt = str(waktu_pulang).split(".")[0] if waktu_pulang else "-"
        status_pulang_txt = status_pulang if status_pulang else "Belum Pulang"
        
        table_data.append([
            Paragraph(str(nama), small_style),
            Paragraph(str(kelas), small_style),
            Paragraph(str(jurusan), small_style),
            Paragraph(str(status), small_style),
            Paragraph(waktu_fmt, small_style),
            Paragraph(status_pulang_txt, small_style),
            Paragraph(waktu_pulang_fmt, small_style)
        ])

    col_widths = [70, 40, 80, 80, 70, 80, 70]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))

    elements.append(table)
    doc.build(elements)

    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name="laporan_absensi.pdf",
                     mimetype="application/pdf"
    )



# Replace route /admin/absensi/print di app.py
@app.route("/admin/absensi/print")
@login_required
def print_absensi():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT nama, kelas, jurusan, status, waktu, 
               status_pulang, waktu_pulang 
        FROM absensi 
        ORDER BY waktu DESC
    """)
    absensi = cur.fetchall()
    conn.close()

    return render_template("admin/print_absensi.html", absensi=absensi)

@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM admin WHERE id = ?", (session['admin_id'],))
        row = cur.fetchone()

        if new_password != confirm_password:
            flash("Password baru dan konfirmasi tidak sama!", "error")
        elif not row or not check_password_hash(row[0], old_password):
            flash("Password lama salah!", "error")
        else:
            # Update password
            new_hash = generate_password_hash(new_password)
            cur.execute("UPDATE admin SET password_hash = ? WHERE id = ?", (new_hash, session['admin_id']))
            conn.commit()
            flash("Password berhasil diubah!", "success")

        conn.close()

    return render_template("admin/settings.html", admin_username=session.get('admin_username'))

# ---------------- Initialize Database and Admin ----------------
def init_app():
    """Initialize database and create default admin"""
    buat_tabel()
    auto_migrate_database()  # ← TAMBAHKAN INI
    buat_admin_default()

# Initialize saat import
try:
    init_app()
except Exception as e:
    print(f"Warning: Database initialization failed: {e}")


# ============= ERROR HANDLERS =============
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"Internal Server Error: {e}")
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled Exception: {e}")
    return render_template('500.html'), 500

# ---------------- Main ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 5000))
#     debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
#     # app.run(host="0.0.0.0", port=port, debug=debug_mode)
#     app.run(debug=True)