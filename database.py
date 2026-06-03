from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Reserva(Base):
    __tablename__ = "reservas"

    id       = Column(Integer, primary_key=True, index=True)
    nombre   = Column(String, nullable=False)
    telefono = Column(String, nullable=False)
    fecha    = Column(String, nullable=False)
    hora     = Column(String, nullable=False)
    personas = Column(Integer, nullable=False)
    notas    = Column(String, default="")
    estado   = Column(String, default="confirmada")
    creada   = Column(DateTime, default=datetime.now)

def init_db():
    Base.metadata.create_all(bind=engine)