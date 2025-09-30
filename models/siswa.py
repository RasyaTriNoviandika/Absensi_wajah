from sqlalchemy import Column, Integer, String
from . import Base

class Siswa(Base):
    __tablename__ = "siswa"

    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String, nullable=False)
    nis = Column(String, unique=True, index=True)
