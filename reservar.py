import os
import sys
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError


MADRID = ZoneInfo("Europe/Madrid")

LOGIN_URL = "https://sport.nubapp.com/api/v4/login"
BOOKING_URL = "https://sport.nubapp.com/api/v4/bookings/setBooking.php"

USERNAME = os.environ["NUBAPP_USERNAME"]
PASSWORD = os.environ["NUBAPP_PASSWORD"]
ID_USER = os.environ["NUBAPP_ID_USER"]
ID_APPLICATION = os.environ.get("NUBAPP_ID_APPLICATION", "94168645")

TARGET_WEEKDAY = os.environ.get(
    "TARGET_WEEKDAY",
    "thursday",
).strip().lower()

FROM_TIME = os.environ.get("FROM_TIME", "20:00")
TO_TIME = os.environ.get("TO_TIME", "21:00")
ID_CATEGORY = os.environ.get("ID_CATEGORY", "3967")
ID_FACILITY = os.environ.get("ID_FACILITY", "10997")
BOOKED_ON = os.environ.get("BOOKED_ON", "3")

OPEN_HHMM = os.environ.get("OPEN_HHMM", "08:00")

EARLY_SECONDS = float(
    os.environ.get("EARLY_SECONDS", "0.30")
)

BURST_SECONDS = float(
    os.environ.get("BURST_SECONDS", "3.0")
)

DEADLINE_SECONDS = float(
    os.environ.get("DEADLINE_SECONDS", "60")
)

BURST_SLEEP = float(
    os.environ.get("BURST_SLEEP", "0.05")
)

NORMAL_SLEEP = float(
    os.environ.get("NORMAL_SLEEP", "0.25")
)


def log(msg: str) -> None:
    print(
        f"[{datetime.now(MADRID).isoformat()}] {msg}",
        flush=True,
    )


def do_login() -> str:
    data = urllib.parse.urlencode(
        {
            "username": USERNAME,
            "password": PASSWORD,
            "id_application": ID_APPLICATION,
        }
    ).encode()

    req = urllib.request.Request(
        LOGIN_URL,
        data=data,
        method="POST",
    )

    req.add_header(
        "content-type",
        "application/x-www-form-urlencoded;charset=UTF-8",
    )
    req.add_header(
        "accept",
        "application/json, text/plain, */*",
    )
    req.add_header("nubapp-origin", "user_apps")
    req.add_header(
        "origin",
        "https://centro.resasports.com",
    )
    req.add_header(
        "referer",
        "https://centro.resasports.com/",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_body = resp.read().decode(
                errors="replace"
            )

    except HTTPError as exc:
        error_body = exc.read().decode(
            errors="replace"
        )
        raise RuntimeError(
            f"Login rechazado HTTP {exc.code}: "
            f"{error_body[:500]}"
        ) from exc

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Respuesta de login no válida: "
            f"{raw_body[:500]}"
        ) from exc

    token = body.get("token")

    if not token:
        raise RuntimeError(
            "El login no devolvió token. "
            f"Campos recibidos: {list(body.keys())}"
        )

    return token


def do_booking(
    token: str,
    target_date: str,
):
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

    req = urllib.request.Request(
        BOOKING_URL,
        data=encoded,
        method="POST",
    )

    req.add_header(
        "content-type",
        "application/x-www-form-urlencoded",
    )
    req.add_header(
        "accept",
        "application/json, text/plain, */*",
    )
    req.add_header(
        "authorization",
        f"Bearer {token}",
    )
    req.add_header("nubapp-origin", "user_apps")
    req.add_header(
        "origin",
        "https://centro.resasports.com",
    )
    req.add_header(
        "referer",
        "https://centro.resasports.com/",
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=15,
        ) as resp:
            body = resp.read().decode(
                errors="replace"
            )
            return resp.status, body

    except HTTPError as exc:
        body = exc.read().decode(
            errors="replace"
        )
        return exc.code, body

    except URLError as exc:
        raise RuntimeError(
            f"Error de conexión con Nubapp: {exc}"
        ) from exc


def parse_open_time(now: datetime) -> datetime:
    parts = OPEN_HHMM.strip().split(":")

    if len(parts) not in (2, 3):
        raise ValueError(
            "OPEN_HHMM debe tener formato "
            f"HH:MM o HH:MM:SS. Valor recibido: "
            f"{OPEN_HHMM!r}"
        )

    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0

    if not 0 <= hour <= 23:
        raise ValueError(
            f"Hora inválida en OPEN_HHMM: {OPEN_HHMM!r}"
        )

    if not 0 <= minute <= 59:
        raise ValueError(
            f"Minuto inválido en OPEN_HHMM: {OPEN_HHMM!r}"
        )

    if not 0 <= second <= 59:
        raise ValueError(
            f"Segundo inválido en OPEN_HHMM: {OPEN_HHMM!r}"
        )

    return now.replace(
        hour=hour,
        minute=minute,
        second=second,
        microsecond=0,
    )


def wait_until(target: datetime) -> None:
    """
    Espera con precisión aproximada:
    - espera gruesa hasta 200 ms antes;
    - espera fina hasta 20 ms antes;
    - busy-wait durante los últimos 20 ms.
    """

    while True:
        remaining = (
            target - datetime.now(MADRID)
        ).total_seconds()

        if remaining <= 0.2:
            break

        time.sleep(0.05)

    while True:
        remaining = (
            target - datetime.now(MADRID)
        ).total_seconds()

        if remaining <= 0.02:
            break

        time.sleep(0.001)

    while datetime.now(MADRID) < target:
        pass


def main() -> None:
    now = datetime.now(MADRID)

    # Se mantiene tu lógica actual de ocho días.
    target_date_obj = now + timedelta(days=8)
    target_date_str = target_date_obj.strftime(
        "%Y-%m-%d"
    )

    log(f"Fecha objetivo: {target_date_str}")
    log(f"OPEN_HHMM recibido: {OPEN_HHMM!r}")

    open_time = parse_open_time(now)

    # Como el workflow se lanza por la noche,
    # la apertura de las 08:00 de hoy ya ha pasado.
    # En ese caso usamos la apertura del día siguiente.
    if open_time <= now:
        open_time += timedelta(days=1)

    burst_start = (
        open_time
        - timedelta(seconds=EARLY_SECONDS)
    )

    burst_end = (
        open_time
        + timedelta(seconds=BURST_SECONDS)
    )

    deadline = (
        open_time
        + timedelta(seconds=DEADLINE_SECONDS)
    )

    # Login 30 segundos antes de la apertura.
    login_time = open_time - timedelta(seconds=30)

    log(f"Apertura configurada: {open_time.isoformat()}")
    log(
        "Inicio de login: "
        f"{login_time.isoformat()}"
    )
    log(
        "Ráfaga empieza en: "
        f"{burst_start.isoformat()} "
        f"(EARLY_SECONDS={EARLY_SECONDS})"
    )
    log(
        "Ráfaga termina en: "
        f"{burst_end.isoformat()} "
        f"(BURST_SECONDS={BURST_SECONDS})"
    )
    log(
        "Deadline en: "
        f"{deadline.isoformat()} "
        f"(DEADLINE_SECONDS={DEADLINE_SECONDS})"
    )

    now = datetime.now(MADRID)

    if now > deadline:
        log(
            "Llegué tarde: el workflow empezó después "
            "del deadline."
        )
        sys.exit(2)

    # Esperar hasta las 07:59:30.
    now = datetime.now(MADRID)

    if now < login_time:
        log(
            "Esperando hasta LOGIN_TIME "
            f"({login_time.isoformat()})..."
        )
        wait_until(login_time)

    # Login fresco 30 segundos antes de la reserva.
    log("Iniciando sesión en Nubapp...")
    token = do_login()
    log("Login OK.")

    # Esperar hasta las 07:59:59.700.
    now = datetime.now(MADRID)

    if now < burst_start:
        log(
            "Esperando hasta BURST_START "
            f"({burst_start.isoformat()})..."
        )
        wait_until(burst_start)

    log(
        "Arranca ráfaga de intentos "
        f"(EARLY {EARLY_SECONDS}s antes de "
        f"{OPEN_HHMM})..."
    )

    attempt = 0

    # Ráfaga agresiva.
    while datetime.now(MADRID) <= burst_end:
        attempt += 1

        try:
            status, body = do_booking(
                token,
                target_date_str,
            )

            log(
                f"BURST intento {attempt}: "
                f"status={status} "
                f"respuesta={body}"
            )

            if status == 200:
                log(
                    "HTTP 200 recibido. "
                    "Comprueba la respuesta para confirmar "
                    "la reserva."
                )
                return

            if status in (401, 403):
                log(
                    f"Autorización rechazada ({status}). "
                    "Renovando token..."
                )
                token = do_login()
                log("Re-login OK.")
                continue

            if status == 429:
                log(
                    "Rate limit (429) en ráfaga. "
                    "Esperando 200 ms..."
                )
                time.sleep(0.2)
                continue

        except Exception as exc:
            log(
                f"BURST intento {attempt} fallo: {exc}"
            )

        time.sleep(BURST_SLEEP)

    # Intentos moderados hasta el deadline.
    log(
        "Fin de ráfaga. Continúo con intentos "
        "moderados hasta deadline..."
    )

    while datetime.now(MADRID) <= deadline:
        attempt += 1

        try:
            status, body = do_booking(
                token,
                target_date_str,
            )

            log(
                f"Intento {attempt}: "
                f"status={status} "
                f"respuesta={body}"
            )

            if status == 200:
                log(
                    "HTTP 200 recibido. "
                    "Comprueba la respuesta para confirmar "
                    "la reserva."
                )
                return

            if status in (401, 403):
                log(
                    f"Autorización rechazada ({status}). "
                    "Renovando token..."
                )
                token = do_login()
                log("Re-login OK.")
                continue

            if status == 429:
                log(
                    "Rate limit (429). "
                    "Esperando 1 segundo..."
                )
                time.sleep(1.0)
                continue

        except Exception as exc:
            log(
                f"Intento {attempt} fallo: {exc}"
            )

        time.sleep(NORMAL_SLEEP)

    log(
        "Se alcanzó el deadline sin completar "
        "la reserva."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
