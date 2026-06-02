from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

engine = create_engine(
    "sqlite:///restaurante.db",
    connect_args={"check_same_thread": False}
)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Reserva(Base):
    __tablename__ = "reservas"

    id       = Column(Integer, primary_key=True, index=True)
    nombre   = Column(String, nullable=False)
    telefono = Column(String, nullable=False)
    fecha    = Column(String, nullable=False)   # YYYY-MM-DD
    hora     = Column(String, nullable=False)   # HH:MM
    personas = Column(Integer, nullable=False)
    notas    = Column(String, default="")
    estado   = Column(String, default="confirmada")  # confirmada | pendiente | cancelada
    creada   = Column(DateTime, default=datetime.now)

def init_db():
    Base.metadata.create_all(bind=engine)
