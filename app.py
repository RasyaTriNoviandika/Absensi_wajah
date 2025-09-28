# =================== UPDATE app.py ===================
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

app = Flask(__name__)

# ============= KONFIGURASI KEAMANAN =============
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'

# ---------------- Konstanta Default ----------------
SCHOOL_LAT = -6.260960
SCHOOL_LNG = 106.959603
RADIUS = 15  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(BASE_DIR, "database.db")
FACES_DIR = os.path.join(BASE_DIR, "faces")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

# Buat folder upload jika belum ada
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(FACES_DIR, exist_ok=True)

print(f"📂 Database path yang dipakai: {DB_NAME}")  # Debug

# ============= FUNGSI KEAMANAN =============
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
            encoding BLOB
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

def get_all_siswa():
    """Ambil semua data siswa"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, nama, kelas, jurusan, foto_path FROM siswa")
    rows = cur.fetchall()
    conn.close()
    return rows

def cari_siswa_dengan_wajah(file_path):
    """Cocokkan wajah dengan data siswa - Version dengan debug info"""
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

        # Bandingkan dengan setiap siswa
        for i, (sid, nama, kelas, jurusan, encoding_str) in enumerate(siswa_list):
            if not encoding_str:
                print(f"⚠️ Siswa {nama} tidak memiliki encoding")
                continue
                
            try:
                encoding_siswa = np.frombuffer(encoding_str, dtype=np.float64)
                print(f"🔄 Membandingkan dengan {nama}...")
                
                # Coba beberapa tolerance level
                tolerances = [0.4, 0.5, 0.6]
                for tolerance in tolerances:
                    result = face_recognition.compare_faces([encoding_siswa], wajah_absen, tolerance=tolerance)
                    distance = face_recognition.face_distance([encoding_siswa], wajah_absen)[0]
                    
                    print(f"   Tolerance {tolerance}: Match={result[0]}, Distance={distance:.3f}")
                    
                    if result[0]:
                        print(f"✅ MATCH FOUND! {nama} (Distance: {distance:.3f})")
                        return {"id": sid, "nama": nama, "kelas": kelas, "jurusan": jurusan}
                        
            except Exception as e:
                print(f"❌ Error parsing encoding untuk {nama}: {e}")
                continue

        print("❌ Tidak ada wajah yang cocok ditemukan")
        return None

    except Exception as e:
        print(f"❌ Error dalam pencocokan wajah: {e}")
        return None

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
@app.route("/register", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        nama = request.form.get("nama")
        kelas = request.form.get("kelas")
        jurusan = request.form.get("jurusan")
        
        if not nama or not kelas or not jurusan:
            flash("Semua field wajib diisi!", "error")
            return redirect(url_for("register_user"))

        # Buat entri siswa dulu (foto_path & encoding kosong sementara)
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO siswa (nama, kelas, jurusan, foto_path, encoding) VALUES (?, ?, ?, ?, ?)",
            (nama, kelas, jurusan, "", None)
        )
        siswa_id = cur.lastrowid
        conn.commit()
        conn.close()

        flash("Registrasi berhasil! Silakan upload foto wajah.", "success")
        return redirect(url_for("potret_user", siswa_id=siswa_id))

    return render_template("user/register.html")

@app.route("/potret/<int:siswa_id>", methods=["GET", "POST"])
def potret_user(siswa_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, nama, kelas, jurusan FROM siswa WHERE id=?", (siswa_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        flash("Siswa tidak ditemukan!", "error")
        return redirect(url_for("register_user"))

    siswa = {"id": row[0], "nama": row[1], "kelas": row[2], "jurusan": row[3]}

    if request.method == "POST":
        file = request.files.get("foto")
        if not file or file.filename == "":
            flash("Foto wajib diupload!", "error")
            return render_template("user/potret.html", siswa=siswa)

        os.makedirs(FACES_DIR, exist_ok=True)
        foto_path = os.path.join(FACES_DIR, f"{uuid.uuid4().hex}.jpg")
        file.save(foto_path)

        try:
            img = face_recognition.load_image_file(foto_path)
            encodings = face_recognition.face_encodings(img)

            if not encodings:
                os.remove(foto_path)
                flash("Wajah tidak terdeteksi, pastikan foto jelas!", "error")
                return render_template("user/potret.html", siswa=siswa)

            if len(encodings) > 1:
                os.remove(foto_path)
                flash("Foto hanya boleh berisi 1 wajah!", "error")
                return render_template("user/potret.html", siswa=siswa)
            
            # Simpan encoding ke database
            encoding = encodings[0]
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute(
                "UPDATE siswa SET foto_path=?, encoding=? WHERE id=?",
                (foto_path, encoding.tobytes(), siswa_id)
            )
            conn.commit()
            conn.close()

            flash("Wajah berhasil disimpan, sekarang Anda bisa absen.", "success")
            return redirect(url_for("index"))

        except Exception as e:
            if os.path.exists(foto_path):
                os.remove(foto_path)
            flash(f"Error saat memproses foto: {str(e)}", "error")
            return render_template("user/potret.html", siswa=siswa)

    return render_template("user/potret.html", siswa=siswa)

@app.route("/absen", methods=["POST"])
def absen():
    """Proses absensi siswa"""
    try:
        file = request.files["foto"]
        lat = float(request.form["lat"])
        lng = float(request.form["lng"])

        filename = f"{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)

        # Ambil area absensi dari DB
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
        row = cur.fetchone()
        conn.close()

        school_lat, school_lng, radius = row
        jarak = hitung_jarak(lat, lng, school_lat, school_lng)

        # Perbaikan logika status yang lebih jelas
        if jarak <= radius:
            status = "HADIR"
        else:
            status = f"TERLAMBAT/DILUAR AREA ({jarak:.0f}m dari sekolah)"

        siswa = cari_siswa_dengan_wajah(filepath)

        # Hapus file temporary
        if os.path.exists(filepath):
            os.remove(filepath)

        if not siswa:
            return jsonify({"success": False, "message": "Wajah tidak dikenali! Pastikan Anda sudah terdaftar."})

        # Waktu lokal WIB
        waktu_lokal = datetime.utcnow() + timedelta(hours=7)
        tanggal_hari_ini = waktu_lokal.date()

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
            return jsonify({"success": False, "message": f"{siswa['nama']} sudah absen hari ini! Silakan absen besok."})

        # Simpan absensi baru
        cur.execute("""
            INSERT INTO absensi (siswa_id, nama, kelas, jurusan, latitude, longitude, status, waktu) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (siswa["id"], siswa["nama"], siswa["kelas"], siswa["jurusan"], lat, lng, status, waktu_lokal))

        conn.commit()
        conn.close()

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
        
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"})

@app.route("/absensi")
def absensi_user():
    """Tabel absensi untuk user"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT nama, kelas, jurusan, status, waktu FROM absensi ORDER BY waktu DESC")
    absensi = cur.fetchall()
    conn.close()
    return render_template("user/absensi.html", absensi=absensi)

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

        if not file or file.filename == '':
            flash("Foto wajah harus diupload!", "error")
            return render_template("admin/register.html")

        os.makedirs(FACES_DIR, exist_ok=True)
        foto_path = os.path.join(FACES_DIR, f"{uuid.uuid4().hex}.jpg")
        file.save(foto_path)

        try:
            img = face_recognition.load_image_file(foto_path)
            encodings = face_recognition.face_encodings(img)
            
            if not encodings:
                os.remove(foto_path)
                flash("Wajah tidak terdeteksi pada foto!", "error")
                return render_template("admin/register.html")
            
            if len(encodings) > 1:
                os.remove(foto_path)
                flash("Gunakan foto dengan 1 wajah saja!", "error")
                return render_template("admin/register.html")

            encoding = encodings[0]

            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO siswa (nama, kelas, jurusan, foto_path, encoding) VALUES (?, ?, ?, ?, ?)",
                (nama, kelas, jurusan, foto_path, encoding.tobytes())
            )
            conn.commit()
            conn.close()

            flash(f"Siswa {nama} berhasil didaftarkan!", "success")
            return redirect(url_for("admin_register"))

        except Exception as e:
            if os.path.exists(foto_path):
                os.remove(foto_path)
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

@app.route("/admin/absensi_map")
@login_required
def admin_absensi_map():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT nama, kelas, jurusan, status, waktu, latitude, longitude
        FROM absensi
        ORDER BY waktu DESC
    """)
    absensi = cur.fetchall()
    conn.close()

    # ambil koordinat sekolah dari settings
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude FROM settings WHERE id=1")
    row = cur.fetchone()
    conn.close()
    school_lat = row[0] if row else SCHOOL_LAT
    school_lng = row[1] if row else SCHOOL_LNG

    return render_template(
        "admin/absensi_map.html",
        absensi=absensi,
        SCHOOL_LAT=school_lat,
        SCHOOL_LNG=school_lng
    )

@app.route("/admin/export/excel")
@login_required
def export_excel():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT nama, kelas, jurusan, status, waktu FROM absensi", conn)
    conn.close()

    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="laporan_absensi.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/admin/export/pdf")
@login_required
def export_pdf():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT nama, kelas, jurusan, status, waktu FROM absensi ORDER BY waktu DESC")
    data = cur.fetchall()
    conn.close()

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Tambah style kecil biar wrap muat
    small_style = ParagraphStyle(
        'small',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=1  # 0=left, 1=center, 2=right
    )

    # Judul
    elements.append(Paragraph("Laporan Absensi", styles['Title']))

    # Header tabel
    table_data = [
        [Paragraph("Nama", small_style),
         Paragraph("Kelas", small_style),
         Paragraph("Jurusan", small_style),
         Paragraph("Status", small_style),
         Paragraph("Waktu", small_style)]
    ]

    # Data tabel
    for row in data:
        nama, kelas, jurusan, status, waktu = row
        waktu_fmt = str(waktu).split(".")[0]  # format tanpa microseconds
        table_data.append([
            Paragraph(str(nama), small_style),
            Paragraph(str(kelas), small_style),
            Paragraph(str(jurusan), small_style),
            Paragraph(str(status), small_style),
            Paragraph(waktu_fmt, small_style)
        ])

    # Atur lebar kolom biar rapi
    col_widths = [90, 50, 120, 120, 90]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
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

@app.route("/admin/absensi/print")
@login_required
def print_absensi():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT nama, kelas, jurusan, status, waktu FROM absensi ORDER BY waktu DESC")
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
    buat_admin_default()

# Initialize saat import
try:
    init_app()
except Exception as e:
    print(f"Warning: Database initialization failed: {e}")

# ---------------- Main ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)  # Enable debug untuk melihat error