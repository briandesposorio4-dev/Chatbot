import os
from groq import Groq
from dotenv import load_dotenv
from database import SessionLocal, Reserva
from datetime import datetime, time
import re

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

conversaciones = {}

# ---------------------------------------------------------------------------
# Helpers de fecha/hora
# ---------------------------------------------------------------------------

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

def fecha_sistema():
    """Retorna fecha/hora actual con contexto completo en español."""
    ahora = datetime.now()
    dia_semana = DIAS_ES[ahora.weekday()]
    dia = ahora.day
    mes = MESES_ES[ahora.month - 1]
    anio = ahora.year
    hora = ahora.strftime("%H:%M")
    return f"{dia_semana} {dia} de {mes} de {anio}, {hora}h"

def normalizar_hora(texto: str):
    """
    Convierte texto libre de hora a HH:MM o None.
    Acepta: '21', '21h', '21:00', '9pm', '9 de la noche', '14:30', '2pm', etc.
    """
    t = texto.strip().lower()

    # Formato HH:MM o H:MM
    m = re.match(r'^(\d{1,2}):(\d{2})$', t)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return f"{h:02d}:{mn:02d}"

    # Solo número: '21', '9', '14'
    m = re.match(r'^(\d{1,2})h?$', t)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"

    # Formato con pm/am: '9pm', '2am', '9 pm'
    m = re.match(r'^(\d{1,2})\s*(am|pm)$', t)
    if m:
        h = int(m.group(1))
        periodo = m.group(2)
        if periodo == 'pm' and h != 12:
            h += 12
        elif periodo == 'am' and h == 12:
            h = 0
        if 0 <= h <= 23:
            return f"{h:02d}:00"

    # Expresiones naturales
    if 'mediodía' in t or 'mediodia' in t:
        return '14:00'
    if 'medianoche' in t:
        return '00:00'

    return None


# ---------------------------------------------------------------------------
# Validación de teléfono
# ---------------------------------------------------------------------------

def telefono_valido(telefono: str) -> bool:
    limpio = re.sub(r"[+\-\s]", "", telefono)
    if not limpio.isdigit():
        return False
    if len(limpio) < 8 or len(limpio) > 15:
        return False
    if len(set(limpio)) == 1:
        return False
    numeros_falsos = ["1234567890", "0123456789", "0000000000", "1111111111"]
    if limpio in numeros_falsos:
        return False
    return True


# ---------------------------------------------------------------------------
# Validación completa de reserva
# ---------------------------------------------------------------------------

def validar_reserva(nombre, telefono, fecha_str, hora_str, personas):
    try:
        if not nombre or len(nombre.strip()) < 2:
            return "El nombre no parece válido."
        if not telefono_valido(telefono):
            return "El teléfono proporcionado no es válido."

        fecha_hora_reserva = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
        ahora = datetime.now()
        if fecha_hora_reserva <= ahora:
            return "Lo siento, esa fecha u hora ya ha pasado."

        fecha = datetime.strptime(fecha_str, "%Y-%m-%d")
        dia_semana = fecha.weekday()  # 0=lunes ... 6=domingo
        hora = datetime.strptime(hora_str, "%H:%M").time()

        if dia_semana in [0, 1, 2]:  # Lun-Mié
            if hora < time(13, 0):
                return "La primera reserva disponible es a las 13:00."
            if hora >= time(17, 0):
                return "Los lunes, martes y miércoles cerramos a las 18:00. La última reserva es a las 17:00."
        else:  # Jue-Dom
            if hora < time(13, 0):
                return "La primera reserva disponible es a las 13:00."
            if hora >= time(23, 0):
                return "Los jueves a domingo cerramos a medianoche. La última reserva es a las 23:00."

        if personas <= 0 or personas > 500:
            return "El número de personas no es válido."

        return None  # Sin error

    except ValueError:
        return "Los datos de la reserva no son válidos. Por favor revisa la fecha y hora."
    except Exception:
        return "Hubo un problema al validar la reserva."


# ---------------------------------------------------------------------------
# Guardar / modificar / cancelar en BD
# ---------------------------------------------------------------------------

def guardar_reserva(texto: str) -> str:
    try:
        for linea in texto.split("\n"):
            linea = linea.strip()
            if not linea.startswith("RESERVA_CONFIRMAR|"):
                continue
            partes = linea.split("|")
            if len(partes) < 6:
                continue
            nombre   = partes[1].strip()
            telefono = partes[2].strip()
            fecha    = partes[3].strip()
            hora     = partes[4].strip()
            personas = int(partes[5].strip())

            error = validar_reserva(nombre, telefono, fecha, hora, personas)
            if error:
                return error

            db = SessionLocal()
            duplicado = db.query(Reserva).filter(
                Reserva.nombre   == nombre,
                Reserva.telefono == telefono,
                Reserva.fecha    == fecha,
                Reserva.hora     == hora,
                Reserva.estado   != "cancelada"
            ).first()
            if duplicado:
                db.close()
                return "Ya tienes una reserva para ese día y hora. Si quieres modificarla dímelo o llama al 91 478 60 54."

            reserva = Reserva(
                nombre=nombre, telefono=telefono,
                fecha=fecha, hora=hora,
                personas=personas, estado="confirmada"
            )
            db.add(reserva)
            db.commit()
            db.close()
            return "¡Perfecto! Tu reserva ha quedado confirmada. ¡Te esperamos! 🎉"

        return "No encontré los datos de la reserva."
    except Exception as e:
        return f"Hubo un problema al guardar la reserva. Por favor llama al 91 478 60 54."


def guardar_reserva_pendiente(texto: str) -> str:
    try:
        for linea in texto.split("\n"):
            linea = linea.strip()
            if not linea.startswith("RESERVA_PENDIENTE|"):
                continue
            partes = linea.split("|")
            if len(partes) < 6:
                continue
            nombre   = partes[1].strip()
            telefono = partes[2].strip()
            fecha    = partes[3].strip()
            hora     = partes[4].strip()
            personas = int(partes[5].strip())

            error = validar_reserva(nombre, telefono, fecha, hora, personas)
            if error:
                return error

            db = SessionLocal()
            reserva = Reserva(
                nombre=nombre, telefono=telefono,
                fecha=fecha, hora=hora,
                personas=personas, estado="pendiente"
            )
            db.add(reserva)
            db.commit()
            db.close()
            return (
                "Tu solicitud ha quedado registrada ✅ "
                "Al ser más de 10 personas, el restaurante se pondrá en contacto contigo para confirmar. "
                "También puedes llamar al 91 478 60 54."
            )

        return "No encontré los datos de la reserva."
    except Exception:
        return "Hubo un problema al registrar la solicitud. Por favor llama al 91 478 60 54."


def modificar_reserva(texto: str) -> str:
    try:
        for linea in texto.split("\n"):
            linea = linea.strip()
            if not linea.startswith("RESERVA_MODIFICAR|"):
                continue
            partes = linea.split("|")
            if len(partes) < 7:
                continue
            nombre       = partes[1].strip()
            telefono     = partes[2].strip()
            nueva_fecha  = partes[3].strip()
            nueva_hora   = partes[4].strip()
            nuevas_pers  = int(partes[5].strip())
            estado_nuevo = "confirmada" if nuevas_pers <= 10 else "pendiente"

            error = validar_reserva(nombre, telefono, nueva_fecha, nueva_hora, nuevas_pers)
            if error:
                return error

            db = SessionLocal()
            reserva = db.query(Reserva).filter(
                Reserva.nombre   == nombre,
                Reserva.telefono == telefono,
                Reserva.estado   != "cancelada"
            ).order_by(Reserva.id.desc()).first()

            if not reserva:
                db.close()
                return "No encontré ninguna reserva activa con esos datos. ¿Quieres hacer una reserva nueva?"

            reserva.fecha    = nueva_fecha
            reserva.hora     = nueva_hora
            reserva.personas = nuevas_pers
            reserva.estado   = estado_nuevo
            db.commit()
            db.close()

            if estado_nuevo == "pendiente":
                return (
                    "Tu reserva ha sido modificada ✅ "
                    "Al ser más de 10 personas, el restaurante te llamará para confirmar."
                )
            return f"¡Listo! Tu reserva ha sido actualizada para el {nueva_fecha} a las {nueva_hora}h. ✅"

        return "No encontré los datos para modificar la reserva."
    except Exception:
        return "Hubo un problema al modificar la reserva. Por favor llama al 91 478 60 54."


def cancelar_reserva(texto: str) -> str:
    try:
        for linea in texto.split("\n"):
            linea = linea.strip()
            if not linea.startswith("RESERVA_CANCELAR|"):
                continue
            partes = linea.split("|")
            if len(partes) < 3:
                continue
            nombre   = partes[1].strip()
            telefono = partes[2].strip()

            if not telefono_valido(telefono):
                return "El teléfono no es válido."

            db = SessionLocal()
            reserva = db.query(Reserva).filter(
                Reserva.nombre   == nombre,
                Reserva.telefono == telefono,
                Reserva.estado   != "cancelada"
            ).order_by(Reserva.id.desc()).first()

            if reserva:
                reserva.estado = "cancelada"
                db.commit()
                db.close()
                return "Tu reserva ha sido cancelada. ¡Esperamos verte pronto! 😊"
            db.close()
            return "No encontré ninguna reserva activa con esos datos. ¿Puede que el nombre o teléfono sean diferentes?"
    except Exception:
        return "Hubo un problema al cancelar. Por favor llama al 91 478 60 54."


# ---------------------------------------------------------------------------
# System prompt (se construye en cada llamada con fecha/hora reales)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_BASE = """Eres el asistente de reservas de La Estación de los Porches, restaurante asador en Madrid.

FECHA Y HORA ACTUAL: {fecha_hora_actual}

Sé breve, claro y amable. Una pregunta a la vez. Sin textos largos. Adapta el idioma al cliente.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INFORMACIÓN DEL RESTAURANTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dirección: Calle Timoteo Pérez Rubio 2, Madrid
Teléfono: 91 478 60 54

HORARIOS:
- Lunes a miércoles: primera reserva 13:00, última 17:00
- Jueves a domingo: primera reserva 13:00, última 23:00

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HACER UNA RESERVA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Recoge los datos en este orden, uno por uno:
1. Nombre completo
2. Teléfono
3. Fecha
4. Hora
5. Número de personas

REGLAS DE FECHA:
- Usa la fecha del sistema para saber qué día es hoy.
- Si el cliente dice "el 16" o "jueves 16", asume que es el mes actual y confirma: "¿El 16 de junio?"
- Si dice "el mes que viene" o similar, usa el mes siguiente.
- Si dice "mañana", "pasado mañana", "el viernes", calcula a partir de la fecha del sistema.
- Nunca aceptes una fecha que ya haya pasado.
- Convierte la fecha a formato YYYY-MM-DD internamente.

REGLAS DE HORA:
- Acepta cualquier formato natural: "a las 9", "21h", "9 de la noche", "2pm", "21:30", etc.
- Si el cliente escribe solo un número (ej: "9"), si es ambiguo pregunta: "¿Las 9 de la mañana (09:00) o de la noche (21:00)?"
- Convierte siempre a HH:MM en formato 24h internamente.
- No se puede reservar una hora que ya haya pasado hoy.
- Respeta los horarios según el día de la semana (ver arriba).

VALIDACIÓN DE TELÉFONO:
- Entre 8 y 15 dígitos (puede tener +, espacios o guiones).
- Rechaza: solo un dígito repetido, secuencias falsas (1234567890, 0000000000).
- Si no es válido, pide otro número.

GRUPOS:
- 10 o menos personas → confirmación automática.
- Más de 10 personas → queda pendiente, el restaurante llama para confirmar.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MODIFICAR UNA RESERVA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pide nombre y teléfono para identificar la reserva.
Luego pregunta qué quiere cambiar (fecha, hora, personas).
Confirma los nuevos datos antes de guardar.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CANCELAR UNA RESERVA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pide nombre y teléfono para identificar la reserva.
Confirma que quiere cancelar antes de proceder.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMANDOS INTERNOS (NO mostrar al cliente)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cuando tengas todos los datos validados, escribe exactamente uno de estos en tu respuesta:

- 10 o menos personas:
  RESERVA_CONFIRMAR|nombre|telefono|YYYY-MM-DD|HH:MM|personas

- Más de 10 personas:
  RESERVA_PENDIENTE|nombre|telefono|YYYY-MM-DD|HH:MM|personas

- Modificar reserva:
  RESERVA_MODIFICAR|nombre|telefono|YYYY-MM-DD_nueva|HH:MM_nueva|personas_nuevas|campo_modificado

- Cancelar reserva:
  RESERVA_CANCELAR|nombre|telefono

IMPORTANTE:
- Confirma siempre los datos con el cliente ANTES de escribir el comando.
- Si el cliente corrige algún dato, actualiza y vuelve a confirmar.
- No repitas el comando si el sistema ya confirmó la acción.
- Nunca inventes datos. Si no estás seguro, pregunta.
"""


# ---------------------------------------------------------------------------
# Procesar mensaje
# ---------------------------------------------------------------------------

def procesar_mensaje(session_id: str, mensaje: str) -> str:
    if session_id not in conversaciones:
        conversaciones[session_id] = []

    conversaciones[session_id].append({"role": "user", "content": mensaje})

    # Inyectar fecha/hora real en cada llamada
    system = SYSTEM_PROMPT_BASE.format(fecha_hora_actual=fecha_sistema())

    try:
        respuesta = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=400,
            temperature=0.3,
            messages=[{"role": "system", "content": system}] + conversaciones[session_id]
        )
        texto = respuesta.choices[0].message.content.strip()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error interno: {str(e)}"
    # Procesar comandos
    resultado = None
    if "RESERVA_CONFIRMAR|" in texto:
        resultado = guardar_reserva(texto)
    elif "RESERVA_PENDIENTE|" in texto:
        resultado = guardar_reserva_pendiente(texto)
    elif "RESERVA_MODIFICAR|" in texto:
        resultado = modificar_reserva(texto)
    elif "RESERVA_CANCELAR|" in texto:
        resultado = cancelar_reserva(texto)

    if resultado:
        # Sustituir el texto técnico por la respuesta limpia
        texto = resultado

    conversaciones[session_id].append({"role": "assistant", "content": texto})
    return texto
