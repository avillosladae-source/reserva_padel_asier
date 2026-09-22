[LEEME.md](https://github.com/user-attachments/files/32529812/LEEME.md)
# Reserva automática de pista — Kirol Zizur

## Qué hace esto
Cada día a las **8:00 (hora de Madrid)**, revisa si hoy es el día de la semana
que configuraste (`TARGET_WEEKDAY`). Si es así, espera hasta las 08:00:00 en
punto, inicia sesión con tu usuario, y reserva la pista configurada para el
día que cae 7 días después, en el horario que hayas puesto.

Se ejecuta en los servidores de GitHub, así que **no necesitas tener el
ordenador ni el móvil encendidos**.

## Pasos para dejarlo funcionando

1. **Crea un repositorio privado en GitHub** (github.com → New repository →
   márcalo como *Private*).

2. **Sube estos dos archivos** manteniendo la misma estructura de carpetas:
   - `reservar.py`
   - `.github/workflows/reserva.yml`

   (Puedes arrastrarlos directamente en la web de GitHub con "Add file →
   Upload files", asegurándote de que `reserva.yml` queda dentro de la ruta
   `.github/workflows/`.)

3. **Añade tus credenciales como "Secrets"** (cifradas, nadie las ve):
   En el repositorio → **Settings → Secrets and variables → Actions →
   New repository secret**. Crea estos tres:
   - `NUBAPP_USERNAME` → tu usuario (ej: `asier3657`)
   - `NUBAPP_PASSWORD` → tu contraseña
   - `NUBAPP_ID_USER` → `3852292`

   ⚠️ Te recomiendo **cambiar tu contraseña** de Kirol Zizur después de
   configurar esto, ya que la compartiste en texto plano durante esta
   conversación. Actualiza también el Secret si la cambias.

4. **Ajusta la configuración** editando el archivo `reserva.yml` (los valores
   bajo `env:`, no hace falta tocar `reservar.py`):
   - `TARGET_WEEKDAY`: día de la semana en el que se debe reservar (en
     inglés y minúscula: `monday`, `tuesday`, `wednesday`, `thursday`,
     `friday`, `saturday`, `sunday`). Recuerda: como el plazo se abre
     siempre 7 días antes, el día en que el script "actúa" es el MISMO día
     de la semana que el día que reserva (si hoy es jueves, reserva el
     jueves de la semana que viene).
   - `FROM_TIME` / `TO_TIME`: horario de la pista.
   - `ID_CATEGORY` / `ID_FACILITY`: qué pista concreta. Si algún día quieres
     otra pista, hay que capturar de nuevo una petición `setBooking.php`
     para esa pista y coger esos dos números.

5. **Pruébalo a mano antes de confiar en él**: en la pestaña **Actions** del
   repositorio, entra en el workflow "Reserva automatica pista padel" y
   pulsa **Run workflow** (botón manual). Mira los "logs" de la ejecución —
   ahí verás mensaje por mensaje qué ha hecho el script (login, intento de
   reserva, respuesta del servidor). Como se ejecuta fuera de la ventana de
   las 08:00, saldrá enseguida diciendo "Fuera de ventana horaria" — eso es
   normal y confirma que el script arranca bien. Si quieres forzar que
   también pruebe la lógica de reserva sin esperar a las 8:00, dímelo y te
   preparo una versión de prueba.

6. **Déjalo correr solo**: a partir de aquí, GitHub lo ejecutará automáticamente
   cada día a las 8:00 hora de Madrid, sin que tengas que hacer nada.

## Cómo saber si funcionó
Revisa los logs en la pestaña **Actions** después de cada ejecución de las
8:00, o simplemente mira tu app de Kirol Zizur — si la pista aparece
reservada a tu nombre, todo ha ido bien.

## Importante
- Revisa el reglamento de Kirol Zizur/Resasports por si prohíbe
  expresamente el uso de scripts o bots para reservar; si el centro lo
  detecta, podría limitar o suspender la cuenta.
- El token de acceso capturado durante la conversación ya ha caducado (dura
  ~1 hora), así que no supone un riesgo dejarlo en el historial del chat.
  Aun así, cambia la contraseña como se indica en el paso 3.
