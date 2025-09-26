// ambil elemen
const video = document.getElementById("camera");
const captureBtn = document.getElementById("capture"); // perbaikan ID
const loading = document.getElementById("loading");

// --- buka kamera ---
navigator.mediaDevices.getUserMedia({ video: true })
  .then(stream => {
    video.srcObject = stream;
    video.play(); // langsung play
  })
  .catch(err => {
    alert("⚠️ Kamera tidak bisa diakses: " + err.message);
  });

// --- event tombol potret ---
captureBtn.addEventListener("click", () => {
  // pause video saat capture
  video.pause();
  loading.style.display = "block"; // tampilkan loading

  // bikin canvas sementara
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0);

  // ubah ke blob dan kirim ke server
  canvas.toBlob(blob => {
    // ambil lokasi GPS
    navigator.geolocation.getCurrentPosition(pos => {
      const formData = new FormData();
      formData.append("foto", blob, "capture.png");
      formData.append("lat", pos.coords.latitude);
      formData.append("lng", pos.coords.longitude);

      fetch("/absen", { method: "POST", body: formData })
        .then(res => {
          if (!res.ok) throw new Error("Server error " + res.status);
          return res.json();
        })
        .then(data => {
          loading.style.display = "none"; // sembunyikan loading
          if (data.success) {
            alert(
              "✅ Absen Berhasil!\n" +
              "Nama: " + data.nama + "\n" +
              "Kelas: " + data.kelas + "\n" +
              "Jurusan: " + data.jurusan + "\n" +
              "Area: " + data.area
            );
          } else {
            alert("❌ Absen Gagal!\n" + data.message);
          }
          video.play(); // lanjut kamera lagi
        })
        .catch(err => {
          loading.style.display = "none";
          alert("⚠️ Terjadi kesalahan!\n" + err.message);
          video.play();
        });
    }, () => {
      loading.style.display = "none";
      alert("⚠️ Lokasi tidak bisa diakses, aktifkan GPS!");
      video.play();
    });
  }, "image/png");
});
