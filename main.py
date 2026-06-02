from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from brain import procesar_mensaje
from database import init_db, SessionLocal, Reserva
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
init_db()

PANEL_PASSWORD = "porches123"


class Mensaje(BaseModel):
    session_id: str
    texto: str

class LoginData(BaseModel):
    password: str

class ModificarData(BaseModel):
    fecha: str | None = None
    hora: str | None = None
    personas: int | None = None
    notas: str | None = None


@app.get("/")
def index():
    return FileResponse("static/index.html")

@app.get("/panel")
def panel():
    return FileResponse("static/login.html")

@app.post("/panel/login")
def login(data: LoginData):
    if data.password == PANEL_PASSWORD:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

@app.get("/panel/reservas")
def panel_reservas():
    return FileResponse("static/panel.html")

@app.post("/chat")
def chat(mensaje: Mensaje):
    respuesta = procesar_mensaje(mensaje.session_id, mensaje.texto)
    return {"respuesta": respuesta}

@app.get("/nueva-sesion")
def nueva_sesion():
    return {"session_id": str(uuid.uuid4())}

@app.get("/reservas")
def listar_reservas():
    db = SessionLocal()
    reservas = db.query(Reserva).order_by(Reserva.fecha, Reserva.hora).all()
    db.close()
    return [
        {
            "id": r.id,
            "nombre": r.nombre,
            "telefono": r.telefono,
            "fecha": r.fecha,
            "hora": r.hora,
            "personas": r.personas,
            "notas": r.notas or "",
            "estado": r.estado,
            "creada": r.creada.isoformat() if r.creada else None,
        }
        for r in reservas
    ]

@app.post("/reservas/{id}/cancelar")
def cancelar(id: int):
    db = SessionLocal()
    r = db.query(Reserva).filter(Reserva.id == id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    r.estado = "cancelada"
    db.commit()
    db.close()
    return {"ok": True}

@app.post("/reservas/{id}/confirmar")
def confirmar(id: int):
    db = SessionLocal()
    r = db.query(Reserva).filter(Reserva.id == id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    r.estado = "confirmada"
    db.commit()
    db.close()
    return {"ok": True}

@app.post("/reservas/{id}/modificar")
def modificar(id: int, data: ModificarData):
    db = SessionLocal()
    r = db.query(Reserva).filter(Reserva.id == id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    if data.fecha is not None:
        r.fecha = data.fecha
    if data.hora is not None:
        r.hora = data.hora
    if data.personas is not None:
        r.personas = data.personas
        r.estado = "pendiente" if data.personas > 10 else "confirmada"
    if data.notas is not None:
        r.notas = data.notas
    db.commit()
    db.close()
    return {"ok": True}

@app.delete("/reservas/{id}")
def eliminar(id: int):
    db = SessionLocal()
    r = db.query(Reserva).filter(Reserva.id == id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    db.delete(r)
    db.commit()
    db.close()
    return {"ok": True}
