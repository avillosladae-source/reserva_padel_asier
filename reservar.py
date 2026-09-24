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

# Hora de apertura (para pruebas: "09:30"; producción: "08:00")
OPEN_HHMM = os.environ.get("OPEN_HHMM", "08:00")

# Cuánto antes arrancar la ráfaga (en segundos). Ej: 0.30 = 300ms antes.
EARLY_SECONDS = float(os.environ.get("EARLY_SECONDS", "0.30"))

# Ventanas
BURST_SECONDS = float(os.environ.get("BURST_SECONDS", "3.0"))      # ráfaga agresiva
DEADLINE_SECONDS = float(os.environ.get("DEADLINE_SECONDS", "60")) # seguir intentando hasta +60s

# Sleeps durante intentos
BURST_SLEEP = float(os.environ.get("BURST_SLEEP", "0.05"))   # 50ms
NORMAL_SLEEP = float(os.environ.get("NORMAL_SLEEP", "0.25")) # 250ms


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


def parse_open_time(now: datetime) -> datetime:
    hh, mm = OPEN_HHMM.split(":")
    return now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)


def wait_until(t: datetime) -> None:
    """
    Espera con buena precisión:
    - duerme “grueso” hasta 200ms antes
    - duerme fino hasta 20ms antes
    - últimos 20ms busy-wait para no pasarse por el scheduler del SO
    """
    # Espera gruesa
    while True:
        remaining = (t - datetime.now(MADRID)).total_seconds()
        if remaining <= 0.2:
            break
        time.sleep(0.05)

    # Espera fina
    while True:
        remaining = (t - datetime.now(MADRID)).total_seconds()
        if remaining <= 0.02:
            break
        time.sleep(0.001)

    # Último tramo: sin sleep
    while datetime.now(MADRID) < t:
        pass


def main() -> None:
    now = datetime.now(MADRID)

    # Fecha objetivo (OJO: en tu texto decías 7 días; aquí está en 8 como tu script original)
    target_date_obj = now + timedelta(days=8)
    target_date_str = target_date_obj.strftime("%Y-%m-%d")
    log(f"Fecha objetivo: {target_date_str}")

    open_time = parse_open_time(now)

    # Ventanas temporales
    burst_start = open_time - timedelta(seconds=EARLY_SECONDS)
    burst_end = open_time + timedelta(seconds=BURST_SECONDS)
    deadline = open_time + timedelta(seconds=DEADLINE_SECONDS)

    log(f"Apertura configurada: {OPEN_HHMM}:00")
    log(f"Ráfaga empieza en: {burst_start.time()} (EARLY_SECONDS={EARLY_SECONDS})")
    log(f"Ráfaga termina en: {burst_end.time()} (BURST_SECONDS={BURST_SECONDS})")
    log(f"Deadline en:       {deadline.time()} (DEADLINE_SECONDS={DEADLINE_SECONDS})")

    # Si llegas demasiado tarde, dilo claro
    now = datetime.now(MADRID)
    if now > deadline:
        log("Llegué tarde (now > deadline). GitHub/runner arrancó tarde o el script se lanzó fuera de ventana.")
        sys.exit(2)

    # Login antes (si quieres aún más margen, puedes mover el workflow más temprano)
    log("Iniciando sesion en Nubapp...")
    token = do_login()
    log("Login OK.")

    # Esperar hasta burst_start (un poco antes de la apertura)
    now = datetime.now(MADRID)
    if now < burst_start:
        log(f"Esperando hasta BURST_START ({burst_start.isoformat()})...")
        wait_until(burst_start)

    log(f"Arranca ráfaga de intentos (EARLY {EARLY_SECONDS}s antes de {OPEN_HHMM})...")

    attempt = 0

    # Ráfaga agresiva (incluye el cruce por open_time)
    while datetime.now(MADRID) <= burst_end:
        attempt += 1
        try:
            status, body = do_booking(token, target_date_str)
            log(f"BURST intento {attempt}: status={status} respuesta={body}")

            if status == 200:
                log("HTTP 200 recibido. Revisa respuesta/app para confirmar la reserva.")
                return

            if status in (401, 403):
                log("Auth no valida (401/403). Re-logueando...")
                token = do_login()
                log("Re-login OK.")

            if status == 429:
                log("Rate limit (429) en ráfaga. Durmiendo 200ms...")
                time.sleep(0.2)
                continue

        except Exception as exc:
            log(f"BURST intento {attempt} fallo: {exc}")

        time.sleep(BURST_SLEEP)

    # Seguimiento hasta deadline
    log("Fin ráfaga. Continúo con intentos moderados hasta deadline...")

    while datetime.now(MADRID) <= deadline:
        attempt += 1
        try:
            status, body = do_booking(token, target_date_str)
            log(f"Intento {attempt}: status={status} respuesta={body}")

            if status == 200:
                log("HTTP 200 recibido. Revisa respuesta/app para confirmar la reserva.")
                return

            if status in (401, 403):
                log("Auth no valida (401/403). Re-logueando...")
                token = do_login()
                log("Re-login OK.")

            if status == 429:
                log("Rate limit (429). Esperando 1s...")
                time.sleep(1.0)
                continue

        except Exception as exc:
            log(f"Intento {attempt} fallo: {exc}")

        time.sleep(NORMAL_SLEEP)

    log("Se alcanzó el deadline sin completar la reserva.")
    sys.exit(1)


if __name__ == "__main__":
    main()
