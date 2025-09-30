from sqlalchemy import Column, Integer, DateTime
from . import Base

class Absensi(Base):
    __tablename__ = "absensi"

    id = Column(Integer, primary_key=True, index=True)
    siswa_id = Column(Integer, nullable=False)
    waktu = Column(DateTime, nullable=False)
