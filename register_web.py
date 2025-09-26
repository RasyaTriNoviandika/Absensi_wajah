import os
import sqlite3
import face_recognition
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import cv2
import base64
import numpy as np
from datetime import datetime

app = Flask(__name__)
app.secret_key = "rahasia123"

DB_NAME = "database.db"
FACES_DIR = "faces"


def buat_tabel():
    """Buat tabel siswa dan absensi jika belum ada"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS siswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            kelas TEXT NOT NULL,
            jurusan TEXT NOT NULL,
            foto_path TEXT NOT NULL,
            encoding BLOB NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS absensi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            waktu TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# Route root → redirect ke register
@app.route("/")
def index():
    return redirect(url_for("register"))


# Halaman registrasi siswa
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nama = request.form["nama"].strip()
        kelas = request.form["kelas"].strip()
        jurusan = request.form["jurusan"].strip()
        file = request.files["foto"]

        if not (nama and kelas and jurusan and file):
            flash("❌ Semua field harus diisi!")
            return redirect(url_for("register"))

        if not os.path.exists(FACES_DIR):
            os.makedirs(FACES_DIR)

        # Simpan foto
        foto_path = os.path.join(FACES_DIR, f"{nama}.jpg")
        file.save(foto_path)

        # Encode wajah
        img = face_recognition.load_image_file(foto_path)
        encodings = face_recognition.face_encodings(img)

        if len(encodings) == 0:
            flash("❌ Wajah tidak terdeteksi pada foto. Coba lagi!")
            os.remove(foto_path)
            return redirect(url_for("register"))

        encoding = encodings[0].tobytes()

        # Simpan ke DB
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO siswa (nama, kelas, jurusan, foto_path, encoding)
            VALUES (?, ?, ?, ?, ?)
        """, (nama, kelas, jurusan, foto_path, encoding))
        conn.commit()
        conn.close()

        flash(f"✅ Siswa {nama} berhasil diregistrasi!")
        # arahkan ke halaman potret
        return redirect(url_for("potret", nama=nama))

    return render_template("register.html")


# Halaman potret untuk absensi
@app.route("/potret", methods=["GET", "POST"])
def potret():
    """
    Halaman potret utama.
    - Jika POST ada data registrasi → simpan ke DB
    - GET → tampilkan webcam untuk absensi
    """
    if request.method == "POST":
        # Proses registrasi murid baru
        nama = request.form.get("nama").strip()
        kelas = request.form.get("kelas").strip()
        jurusan = request.form.get("jurusan").strip()
        file = request.files.get("foto")

        if not (nama and kelas and jurusan and file):
            flash("❌ Semua field harus diisi!")
            return redirect(url_for("potret"))

        if not os.path.exists(FACES_DIR):
            os.makedirs(FACES_DIR)

        # Simpan foto & encode
        foto_path = os.path.join(FACES_DIR, f"{nama}.jpg")
        file.save(foto_path)
        img = face_recognition.load_image_file(foto_path)
        encodings = face_recognition.face_encodings(img)
        if len(encodings) == 0:
            flash("❌ Wajah tidak terdeteksi")
            os.remove(foto_path)
            return redirect(url_for("potret"))

        encoding = encodings[0].tobytes()
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("INSERT INTO siswa (nama, kelas, jurusan, foto_path, encoding) VALUES (?, ?, ?, ?, ?)",
                    (nama, kelas, jurusan, foto_path, encoding))
        conn.commit()
        conn.close()

        flash(f"✅ {nama} berhasil diregistrasi!")
        # langsung ke absensi setelah registrasi
        return redirect(url_for("potret"))

    # GET → tampilkan webcam untuk absensi
    return render_template("potret.html")


# Halaman daftar absensi (GET)
@app.route("/absensi", methods=["GET"])
def tampil_absensi():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT nama, waktu FROM absensi ORDER BY waktu DESC")
    absensi = cur.fetchall()
    conn.close()
    return render_template("absensi.html", absensi=absensi)


# Proses absensi via kamera (POST)
@app.route("/absensi", methods=["POST"])
def absensi():
    try:
        data = request.get_json()
        img_data = data["image"].split(",")[1]  # ambil base64 tanpa header
        img_bytes = base64.b64decode(img_data)

        # ubah jadi array numpy
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # encode wajah dari frame
        wajah_baru = face_recognition.face_encodings(frame)
        if len(wajah_baru) == 0:
            return jsonify({"status": "error", "message": "❌ Wajah tidak terdeteksi"}), 400
        wajah_baru = wajah_baru[0]

        # ambil semua siswa dari DB
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT nama, encoding FROM siswa")
        data_siswa = cur.fetchall()
        conn.close()

        for nama, encoding_blob in data_siswa:
            wajah_dikenal = np.frombuffer(encoding_blob, dtype=np.float64)
            match = face_recognition.compare_faces([wajah_dikenal], wajah_baru)[0]
            if match:
                # simpan absensi
                conn = sqlite3.connect(DB_NAME)
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO absensi (nama, waktu) VALUES (?, ?)",
                    (nama, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()
                conn.close()

                return jsonify({"status": "success", "message": f"✅ Absensi berhasil untuk {nama}"})

        return jsonify({"status": "error", "message": "❌ Wajah tidak dikenali"}), 404

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    buat_tabel()
    app.run(debug=True)
