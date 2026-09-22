"""
Script de reserva automatica de pista de padel (Kirol Zizur / Resasports / Nubapp).

Cada dia, a las 08:00 hora de Madrid, el plazo se abre para el dia que cae
7 dias despues. Como dentro de 7 dias cae siempre en el MISMO dia de la
semana que hoy, este script solo actua si hoy es el dia de la semana que
tu configures (TARGET_WEEKDAY). Si no coincide, no hace nada.

Variables de entorno necesarias (se configuran como "Secrets" en GitHub):
  NUBAPP_USERNAME       -> tu usuario de Kirol Zizur
  NUBAPP_PASSWORD       -> tu contrasena
  NUBAPP_ID_USER        -> tu id de usuario numerico (lo sacamos del token: 3852292)

Variables de configuracion (puedes dejarlas en el propio workflow, no son secretas):
  NUBAPP_ID_APPLICATION -> 94168645
  TARGET_WEEKDAY         -> dia de la semana en ingles y minuscula: monday, tuesday,
                             wednesday, thursday, friday, saturday, sunday
  FROM_TIME               -> hora de inicio de la pista, formato HH:MM (ej: 20:00)
  TO_TIME                 -> hora de fin de la pista, formato HH:MM (ej: 21:00)
  ID_CATEGORY              -> id de categoria de pista (ej: 3967)
  ID_FACILITY              -> id de la pista concreta (ej: 10997)
  BOOKED_ON                -> normalmente "3", tal y como lo capturamos
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")

LOGIN_URL = "https://sport.nubapp.com/api/v4/login"
BOOKING_URL = "https://sport.nubapp.com/api/v4/bookings/setBooking.php"

USERNAME = os.environ["NUBAPP_USERNAME"]
PASSWORD = os.environ["NUBAPP_PASSWORD"]
ID_USER = os.environ["NUBAPP_ID_USER"]
ID_APPLICATION = os.environ.get("NUBAPP_ID_APPLICATION", "94168645")

TARGET_WEEKDAY = os.environ.get("TARGET_WEEKDAY", "thursday").strip().lower()
FROM_TIME = os.environ.get("FROM_TIME", "20:00")
TO_TIME = os.environ.get("TO_TIME", "21:00")
ID_CATEGORY = os.environ.get("ID_CATEGORY", "3967")
ID_FACILITY = os.environ.get("ID_FACILITY", "10997")
BOOKED_ON = os.environ.get("BOOKED_ON", "3")

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def log(msg: str) -> None:
    print(f"[{datetime.now(MADRID).isoformat()}] {msg}", flush=True)


def do_login() -> str:
    data = urllib.parse.urlencode({
        "username": USERNAME,
        "password": PASSWORD,
        "id_application": ID_APPLICATION,
    }).encode()
    req = urllib.request.Request(LOGIN_URL, data=data, method="POST")
    req.add_header("content-type", "application/x-www-form-urlencoded;charset=UTF-8")
    req.add_header("accept", "application/json, text/plain, */*")
    req.add_header("nubapp-origin", "user_apps")
    req.add_header("origin", "https://centro.resasports.com")
    req.add_header("referer", "https://centro.resasports.com/")
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode())
    return body["token"]


def do_booking(token: str, target_date: str):
    data = {
        "app_version": "5.14.01",
        "id_application": ID_APPLICATION,
        "id_user": ID_USER,
        "action_by": ID_USER,
        "id_category": ID_CATEGORY,
        "id_facility": ID_FACILITY,
        "date": target_date,
        "from": FROM_TIME,
        "to": TO_TIME,
        "booked_on": BOOKED_ON,
        "users_on_booking[0][id_user]": ID_USER,
        "users_on_booking[0][n_guests]": "0",
    }
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BOOKING_URL, data=encoded, method="POST")
    req.add_header("content-type", "application/x-www-form-urlencoded")
    req.add_header("accept", "application/json, text/plain, */*")
    req.add_header("authorization", f"Bearer {token}")
    req.add_header("nubapp-origin", "user_apps")
    req.add_header("origin", "https://centro.resasports.com")
    req.add_header("referer", "https://centro.resasports.com/")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, resp.read().decode()


def main() -> None:
    now = datetime.now(MADRID)
    target_date_obj = now + timedelta(days=8)
    target_date_str = target_date_obj.strftime("%Y-%m-%d")

    log(f"Fecha objetivo: {target_date_str}")
    log("Iniciando sesion en Nubapp...")

    token = do_login()
    log("Login OK.")

    # Intentar desde las 07:59:00 hasta las 08:01:00
    start_time = now.replace(hour=7, minute=59, second=0, microsecond=0)
    deadline = now.replace(hour=8, minute=1, second=0, microsecond=0)

    # Si el script se ejecuta antes de las 07:59, esperamos.
    if now < start_time:
        seconds_to_wait = (start_time - now).total_seconds()
        log(f"Esperando hasta las 07:59:00 ({seconds_to_wait:.1f} segundos)...")
        time.sleep(seconds_to_wait)

    attempt = 0

    while datetime.now(MADRID) <= deadline:
        attempt += 1

        try:
            status, body = do_booking(token, target_date_str)

            log(f"Intento {attempt}: status={status} respuesta={body}")

            if status == 200:
                log("Peticion aceptada por el servidor. Revisa la app/web para confirmar la reserva.")
                return

        except Exception as exc:
            log(f"Intento {attempt} fallo: {exc}")

        time.sleep(1)

    log("Se alcanzo la hora limite de las 08:01 sin completar la reserva.")
    sys.exit(1)

if __name__ == "__main__":
    main()
