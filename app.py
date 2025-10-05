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

# ============= KONFIGURASI KEAMANAN =============
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or get_or_create_secret_key()
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'

# ---------------- Konstanta Default ----------------
SCHOOL_LAT = -6.2704913253598
SCHOOL_LNG = 106.96107261359252
RADIUS = 15  

DB_NAME = "database.db"
FACES_DIR = "faces"
UPLOAD_DIR = "uploads"

# Buat folder upload jika belum ada
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Face Recognition Thresholds
FACE_RECOGNITION_THRESHOLD = 0.45
FACE_DUPLICATE_THRESHOLD = 0.4

# Maximum upload file size: 5MB
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Allowed extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

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
        password_hash = generate_password_hash('admin123')
        cur.execute(
            "INSERT INTO admin (username, password_hash) VALUES (?, ?)",
            ('admin', password_hash)
        )
        conn.commit()
        print("✅ Admin default dibuat - Username: admin, Password: admin123")
    
    conn.close()

# ---------------- Database ----------------
def buat_tabel():
    """Membuat tabel utama jika belum ada"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Tabel siswa
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

    # Tabel absensi
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

    # Tabel settings (untuk area absensi)
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
    cur.execute("SELECT id, nama, kelas, jurusan, foto_path FROM siswa")
    rows = cur.fetchall()
    conn.close()
    return rows

def cari_siswa_dengan_wajah(file_path):
    """Cocokkan wajah dengan data siswa - Version dengan algoritma yang lebih akurat"""
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

        # ============= ALGORITMA BARU: CARI YANG PALING MIRIP =============
        best_match = None
        best_distance = float('inf')
        
        # Bandingkan dengan setiap siswa
        for i, (sid, nama, kelas, jurusan, encoding_str) in enumerate(siswa_list):
            if not encoding_str:
                print(f"⚠️ Siswa {nama} tidak memiliki encoding")
                continue
                
            try:
                encoding_siswa = ast.literal_eval(encoding_str)
                
                # Hitung jarak (distance) - semakin kecil semakin mirip
                distance = face_recognition.face_distance([encoding_siswa], wajah_absen)[0]
                
                print(f"🔄 {i+1}. {nama}: Distance = {distance:.4f}")
                
                # Simpan yang paling mirip
                if distance < best_distance:
                    best_distance = distance
                    best_match = {
                        "id": sid,
                        "nama": nama,
                        "kelas": kelas,
                        "jurusan": jurusan,
                        "distance": distance
                    }
                        
            except Exception as e:
                print(f"❌ Error parsing encoding untuk {nama}: {e}")
                continue

        # ============= VALIDASI DENGAN THRESHOLD KETAT =============
        # Threshold: 0.4 = sangat ketat, 0.6 = normal
        THRESHOLD = 0.45  # Ubah ini jika terlalu ketat/longgar
        
        if best_match and best_distance < THRESHOLD:
            print(f"✅ MATCH FOUND! {best_match['nama']} (Distance: {best_distance:.4f})")
            return best_match
        else:
            if best_match:
                print(f"❌ Wajah paling mirip: {best_match['nama']} (Distance: {best_distance:.4f})")
                print(f"⚠️ Namun jarak ({best_distance:.4f}) melebihi threshold ({THRESHOLD})")
            print("❌ Tidak ada wajah yang cocok dengan confidence tinggi")
            return None

    except Exception as e:
        print(f"❌ Error dalam pencocokan wajah: {e}")
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
# ============= PERBAIKAN ROUTE REGISTER_USER - DENGAN VALIDASI DUPLIKASI =============
@app.route("/register", methods=["GET", "POST"])
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
        
        # ✅ INDENTASI BENAR - Simpan foto sementara untuk pengecekan
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        temp_foto_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4().hex}.jpg")
        file.save(temp_foto_path)

        try:
            # ============= CEK DUPLIKASI WAJAH TERLEBIH DAHULU =============
            siswa_duplikat = cek_wajah_sudah_terdaftar(temp_foto_path)
            
            if siswa_duplikat:
                # Hapus foto temporary
                os.remove(temp_foto_path)
                # Clear session temp
                session.pop('temp_nama', None)
                session.pop('temp_kelas', None) 
                session.pop('temp_jurusan', None)
                session.pop('_flashes', None)
                
                flash(f"⚠️ Wajah Anda sudah terdaftar atas nama '{siswa_duplikat['nama']}' (Nomor Absen: {siswa_duplikat.get('nomor_absen', 'N/A')}) dari kelas {siswa_duplikat['kelas']} {siswa_duplikat['jurusan']}. Tidak dapat mendaftar ulang!", "error")
                return redirect(url_for("absen_harian"))

            # ============= PROSES ENCODING JIKA TIDAK ADA DUPLIKASI =============
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

            # Simpan siswa ke database DENGAN NOMOR ABSEN
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO siswa (nama, kelas, jurusan, foto_path, encoding, nomor_absen) VALUES (?, ?, ?, ?, ?, ?)",
                (siswa['nama'], siswa['kelas'], siswa['jurusan'], final_foto_path, str(encoding), nomor_absen)
            )
            conn.commit()
            conn.close()

            # Hapus session temporary setelah berhasil
            session.pop('temp_nama', None)
            session.pop('temp_kelas', None)
            session.pop('temp_jurusan', None)
            session.pop('_flashes', None)

            flash(f"🎉 Registrasi berhasil! {siswa['nama']} (Nomor Absen: {nomor_absen}) sekarang bisa melakukan absensi.", "success")
            return redirect(url_for("absen_harian"))

        except Exception as e:
            # Hapus file temp jika ada error
            if os.path.exists(temp_foto_path):
                os.remove(temp_foto_path)
            flash(f"Error memproses foto: {str(e)}", "error")
            return render_template("user/potret.html", siswa=siswa)

    return render_template("user/potret.html", siswa=siswa)

@app.route("/absen", methods=["POST"])
def absen():
    """Proses absensi siswa dengan logging detail"""
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
        print(f"📍 Lokasi: {lat}, {lng}")
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

        # Perbaikan logika status area
        if jarak <= radius:
            status = "HADIR"
            print(f"✅ Status lokasi: DALAM AREA")
        else:
            status = f"DILUAR AREA ({jarak:.0f}m dari sekolah)"
            print(f"⚠️ Status lokasi: DILUAR AREA")

        # PENCOCOKAN WAJAH
        print(f"\n🔍 Memulai pencocokan wajah...")
        siswa = cari_siswa_dengan_wajah(filepath)

        # Hapus file temporary
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"🗑️ File temporary dihapus")

        if not siswa:
            print(f"\n❌ ABSENSI GAGAL: Wajah tidak dikenali\n")
            return jsonify({
                "success": False, 
                "message": "Wajah tidak dikenali! Pastikan Anda sudah terdaftar dan foto jelas."
            })

        print(f"\n✅ Wajah dikenali: {siswa['nama']}")
        print(f"📊 Confidence: {1 - siswa['distance']:.2%}")

        # Waktu lokal WIB
        waktu_lokal = datetime.utcnow() + timedelta(hours=7)
        tanggal_hari_ini = waktu_lokal.date()
        jam_sekarang = waktu_lokal.time()

        # ✅ VALIDASI JAM MASUK (misalnya 06:00 - 07:30 WIB)
        jam_mulai_masuk = datetime.strptime("06:00", "%H:%M").time()
        jam_akhir_masuk = datetime.strptime("07:30", "%H:%M").time()

        if jam_sekarang > jam_akhir_masuk:
            status = "TERLAMBAT"
            print(f"⏰ Status waktu: TERLAMBAT")
        elif jam_sekarang < jam_mulai_masuk:
            print(f"⏰ Belum waktunya absen masuk")
            return jsonify({
                "success": False,
                "message": f"Absen masuk hanya bisa dilakukan mulai jam 06:00 WIB. Sekarang jam {waktu_lokal.strftime('%H:%M')} WIB."
            })
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
                "message": f"{siswa['nama']} sudah absen hari ini! Silakan absen besok."
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

        return jsonify({
            "success": True,
            "redirect": url_for("absensi_user"),
            "nama": siswa["nama"],
            "kelas": siswa["kelas"],
            "jurusan": siswa["jurusan"],
            "status": status
        })

    except Exception as e:
        # Hapus file jika ada error
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"})

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

            if distance < 0.45:  # threshold
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
@app.route("/absensi")
def absensi_user():
    """Tabel absensi untuk user - dengan data pulang dan nomor absen"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Cek dulu apakah kolom status_pulang ada
    cur.execute("PRAGMA table_info(absensi)")
    columns = [col[1] for col in cur.fetchall()]
    
    if 'status_pulang' in columns:
        # Jika kolom sudah ada, pakai query lengkap dengan JOIN
        cur.execute("""
            SELECT a.nama, a.kelas, a.jurusan, a.status, a.waktu, 
                   a.status_pulang, a.waktu_pulang,
                   COALESCE(s.nomor_absen, '-') as nomor_absen
            FROM absensi a
            LEFT JOIN siswa s ON a.siswa_id = s.id
            ORDER BY a.waktu DESC
        """)
    else:
        # Jika kolom belum ada (fallback)
        cur.execute("""
            SELECT a.nama, a.kelas, a.jurusan, a.status, a.waktu, 
                   NULL as status_pulang, NULL as waktu_pulang,
                   COALESCE(s.nomor_absen, '-') as nomor_absen
            FROM absensi a
            LEFT JOIN siswa s ON a.siswa_id = s.id
            ORDER BY a.waktu DESC
        """)
    
    absensi = cur.fetchall()
    conn.close()
    return render_template("user/absensi.html", absensi=absensi)

# ============= ROUTE ABSEN PULANG =============
@app.route("/absen_pulang", methods=["POST"])
def absen_pulang():
    try:
        file = request.files["foto"]
        lat = float(request.form["lat"])
        lng = float(request.form["lng"])

        filename = f"pulang_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)

        # Ambil area absensi dari DB
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
        row = cur.fetchone()
        conn.close()

        school_lat, school_lng, radius = row

        # Cek lokasi
        valid, jarak = dalam_radius(lat, lng, school_lat, school_lng, radius)

        if valid:
            status_pulang = "PULANG TEPAT WAKTU"
        else:
            status_pulang = f"PULANG DILUAR AREA ({jarak:.0f}m dari sekolah)"

        # Cari siswa dengan wajah
        siswa = cari_siswa_dengan_wajah(filepath)

        # Hapus file temporary
        if os.path.exists(filepath):
            os.remove(filepath)

        if not siswa:
            return jsonify({"success": False, "message": "Wajah tidak dikenali! Pastikan Anda sudah terdaftar."})

        # Waktu lokal WIB
        waktu_lokal = datetime.utcnow() + timedelta(hours=7)
        tanggal_hari_ini = waktu_lokal.date()
        jam_sekarang = waktu_lokal.time()

        # ✅ VALIDASI JAM PULANG (hanya bisa absen pulang jam 15:00 - 17:00)
        jam_mulai_pulang = datetime.strptime("10:00", "%H:%M").time()
        jam_akhir_pulang = datetime.strptime("17:00", "%H:%M").time()

        if not (jam_mulai_pulang <= jam_sekarang <= jam_akhir_pulang):
            return jsonify({
                "success": False, 
                "message": f"Absen pulang hanya bisa dilakukan antara jam 15:00 - 17:00 WIB. Sekarang jam {waktu_lokal.strftime('%H:%M')} WIB."
            })

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        # Cek apakah sudah absen masuk hari ini
        cur.execute("""
            SELECT id, waktu_pulang FROM absensi
            WHERE siswa_id = ? AND DATE(waktu) = ?
        """, (siswa["id"], tanggal_hari_ini))
        absen_hari_ini = cur.fetchone()

        if not absen_hari_ini:
            conn.close()
            return jsonify({
                "success": False, 
                "message": f"{siswa['nama']} belum absen masuk hari ini! Silakan absen masuk terlebih dahulu."
            })

        # Cek apakah sudah absen pulang
        if absen_hari_ini[1] is not None:
            conn.close()
            return jsonify({
                "success": False, 
                "message": f"{siswa['nama']} sudah absen pulang hari ini!"
            })

        # Update absensi dengan data pulang
        cur.execute("""
            UPDATE absensi 
            SET waktu_pulang = ?, status_pulang = ?, latitude_pulang = ?, longitude_pulang = ?
            WHERE id = ?
        """, (waktu_lokal, status_pulang, lat, lng, absen_hari_ini[0]))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "redirect": url_for("absensi_user"),
            "nama": siswa["nama"],
            "kelas": siswa["kelas"],
            "jurusan": siswa["jurusan"],
            "status": status_pulang,
            "waktu": waktu_lokal.strftime("%H:%M:%S")
        })

    except Exception as e:
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"})


@app.route("/absen_pulang_harian", methods=["GET"])
def absen_pulang_harian():
    """Halaman absensi pulang - hanya bisa diakses jam 15:00-17:00"""
    
    # Waktu lokal WIB
    waktu_lokal = datetime.utcnow() + timedelta(hours=7)
    jam_sekarang = waktu_lokal.time()
    
    # Validasi jam
    jam_mulai_pulang = datetime.strptime("10:00", "%H:%M").time()
    jam_akhir_pulang = datetime.strptime("17:00", "%H:%M").time()
    
    if not (jam_mulai_pulang <= jam_sekarang <= jam_akhir_pulang):
        flash(f"⏰ Absen pulang hanya bisa dilakukan antara jam 15:00 - 17:00 WIB. Sekarang jam {waktu_lokal.strftime('%H:%M')} WIB.", "warning")
        return redirect(url_for("index"))
    
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
    """Tabel absensi untuk admin"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT nama, kelas, jurusan, status, waktu, latitude, longitude
        FROM absensi
        ORDER BY waktu DESC
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
            "lng": r[6]
        }
        for r in rows
    ]

    return render_template(
        "admin/absensi.html",
        absensi=absensi,
        SCHOOL_LAT=SCHOOL_LAT,
        SCHOOL_LNG=SCHOOL_LNG
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

# Update route /admin/absensi_map di app.py
@app.route("/admin/absensi_map")
@login_required
def admin_absensi_map():
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        # Cek dulu kolom apa saja yang ada
        cur.execute("PRAGMA table_info(absensi)")
        columns = [col[1] for col in cur.fetchall()]
        
        # Query dengan JOIN ke tabel siswa untuk ambil nomor_absen
        if all(col in columns for col in ['status_pulang', 'waktu_pulang', 'latitude_pulang', 'longitude_pulang']):
            cur.execute("""
                SELECT a.nama, a.kelas, a.jurusan, a.status, a.waktu, a.latitude, a.longitude,
                       COALESCE(a.status_pulang, '') as status_pulang, 
                       COALESCE(a.waktu_pulang, '') as waktu_pulang, 
                       COALESCE(a.latitude_pulang, 0) as latitude_pulang, 
                       COALESCE(a.longitude_pulang, 0) as longitude_pulang,
                       COALESCE(s.nomor_absen, '-') as nomor_absen
                FROM absensi a
                LEFT JOIN siswa s ON a.siswa_id = s.id
                ORDER BY a.waktu DESC
            """)
        else:
            cur.execute("""
                SELECT a.nama, a.kelas, a.jurusan, a.status, a.waktu, a.latitude, a.longitude,
                       '' as status_pulang, 
                       '' as waktu_pulang, 
                       0 as latitude_pulang, 
                       0 as longitude_pulang,
                       COALESCE(s.nomor_absen, '-') as nomor_absen
                FROM absensi a
                LEFT JOIN siswa s ON a.siswa_id = s.id
                ORDER BY a.waktu DESC
            """)
        
        absensi = cur.fetchall()
        
        # Ambil koordinat sekolah dari settings
        cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
        row = cur.fetchone()
        conn.close()
        
        school_lat = row[0] if row else SCHOOL_LAT
        school_lng = row[1] if row else SCHOOL_LNG
        school_radius = row[2] if row else RADIUS

        return render_template(
            "admin/absensi_map.html",
            absensi=absensi,
            SCHOOL_LAT=school_lat,
            SCHOOL_LNG=school_lng,
            RADIUS=school_radius
        )
        
    except Exception as e:
        print(f"❌ Error di absensi_map: {e}")
        flash(f"Error memuat data absensi: {str(e)}", "error")
        return redirect(url_for("admin_index"))

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
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host="0.0.0.0", port=port, debug=debug_mode)