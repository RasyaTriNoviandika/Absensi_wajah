from models import SessionLocal, Base, engine
from models import siswa, absensi  # import semua model biar ke-create

# Buat tabel kalau belum ada
Base.metadata.create_all(bind=engine)

# Dependency untuk ambil session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
