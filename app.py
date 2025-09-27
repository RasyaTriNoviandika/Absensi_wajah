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
from PIL import Image, ImageOps
import numpy as np


app = Flask(__name__)

# ============= KONFIGURASI KEAMANAN =============
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'

# ---------------- Konstanta Default ----------------
SCHOOL_LAT = -6.260960
SCHOOL_LNG = 106.959603
RADIUS = 15  

DB_NAME = "database.db"
FACES_DIR = "faces"
UPLOAD_DIR = "uploads"

# Buat folder upload jika belum ada
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
    """Cocokkan wajah dengan data siswa"""
    try:
        img_unknown = face_recognition.load_image_file(file_path)
        unknown_encodings = face_recognition.face_encodings(img_unknown)
        if not unknown_encodings:
            return None

        wajah_absen = unknown_encodings[0]

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, nama, kelas, jurusan, encoding FROM siswa")
        siswa_list = cur.fetchall()
        conn.close()

        for sid, nama, kelas, jurusan, encoding_str in siswa_list:
            if not encoding_str:
                continue
            try:
                encoding = ast.literal_eval(encoding_str)
            except Exception:
                continue

            result = face_recognition.compare_faces([encoding], wajah_absen, tolerance=0.5)
            if result[0]:
                return {"id": sid, "nama": nama, "kelas": kelas, "jurusan": jurusan}

        return None
    except Exception as e:
        print("Error pencocokan wajah:", e)
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
    return redirect(url_for("register_user"))

# -------- USER (Tidak perlu login) --------
@app.route("/register", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        nama = request.form["nama"]
        kelas = request.form["kelas"]
        jurusan = request.form["jurusan"]
        file = request.files["foto"]

        os.makedirs(FACES_DIR, exist_ok=True)
        foto_path = os.path.join(FACES_DIR, f"{uuid.uuid4().hex}.jpg")
        file.save(foto_path)

        # 🔹 Perbaiki orientasi & resize foto
        try:
            img = Image.open(foto_path)
            img = ImageOps.exif_transpose(img)
            if img.width > 800:
                ratio = 800 / float(img.width)
                new_height = int(img.height * ratio)
                img = img.resize((800, new_height))
            img.save(foto_path)
        except Exception as e:
            os.remove(foto_path)
            return f"Gagal memproses foto: {e}", 400

        # Encode wajah
        img_array = face_recognition.load_image_file(foto_path)
        encodings = face_recognition.face_encodings(img_array)
        if not encodings:
            os.remove(foto_path)
            return "Wajah tidak terdeteksi, coba lagi!", 400

        encoding = encodings[0].tolist()  # ubah jadi list

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO siswa (nama, kelas, jurusan, foto_path, encoding) VALUES (?, ?, ?, ?, ?)",
            (nama, kelas, jurusan, foto_path, str(encoding))
        )
        conn.commit()
        conn.close()

        return redirect(url_for("potret_user"))

    return render_template("user/register.html")

@app.route("/absen", methods=["POST"])
def absen():
    """Proses absensi siswa"""
    file = request.files["foto"]
    lat = float(request.form["lat"])
    lng = float(request.form["lng"])

    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    # 🔹 Perbaiki orientasi & resize foto
    try:
        img = Image.open(filepath)
        img = ImageOps.exif_transpose(img)
        if img.width > 800:
            ratio = 800 / float(img.width)
            new_height = int(img.height * ratio)
            img = img.resize((800, new_height))
        img.save(filepath)
    except Exception as e:
        os.remove(filepath)
        return jsonify({"success": False, "message": f"Gagal memproses foto: {e}"})

    # Ambil area absensi dari DB
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude, radius FROM settings WHERE id=1")
    row = cur.fetchone()
    conn.close()

    school_lat, school_lng, radius = row
    jarak = hitung_jarak(lat, lng, school_lat, school_lng)

    status = "HADIR" if jarak <= radius else f"HADIR (Diluar area, {jarak:.2f} m)"

    siswa = cari_siswa_dengan_wajah(filepath)

    if os.path.exists(filepath):
        os.remove(filepath)

    if not siswa:
        return jsonify({"success": False, "message": "Wajah tidak dikenali!"})

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
        return jsonify({"success": False, "message": f"{siswa['nama']} Sudah Absen Silahkan Absen Untuk Besok hari!"})

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

@app.route("/admin/register")
@login_required
def admin_register():
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
    message_category = None
    message_text = None

    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM admin WHERE id = ?", (session['admin_id'],))
        row = cur.fetchone()

        if new_password != confirm_password:
            message_category = "error"
            message_text = "Password baru dan konfirmasi tidak sama!"
        elif not row or not check_password_hash(row[0], old_password):
            message_category = "error"
            message_text = "Password lama salah!"
        else:
            # Update password
            new_hash = generate_password_hash(new_password)
            cur.execute("UPDATE admin SET password_hash = ? WHERE id = ?", (new_hash, session['admin_id']))
            conn.commit()
            message_category = "success"
            message_text = "Password berhasil diubah!"

        conn.close()

        if message_text:
            flash(message_text, message_category)
            # render halaman langsung, jangan redirect agar flash muncul
            return render_template("admin/settings.html", admin_username=session.get('admin_username'))

    return render_template("admin/settings.html", admin_username=session.get('admin_username'))

# ---------------- Main ----------------
if __name__ == "__main__":
    try:
        buat_tabel()
        buat_admin_default()
        print("✅ Database & admin default siap")
    except Exception as e:
        print(f"⚠️ Error saat inisialisasi DB: {e}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
