# Portal del trabajador /mi-asistencia (MYK-425, MYK-410 item 7)

Consulta de **lectura-unica** con la que cada trabajador conoce sus propias
marcas de asistencia y horas extra del periodo — derecho LFT 132-XVII.

## Autenticación

- Credencial propia por empleado: `employee_code` + **PIN** (4-8 dígitos, el
  generador de RRHH emite 6).
- El PIN se guarda como **hash Argon2id** en `employees.pin_hash`
  (migración `009_employee_portal_pin.sql`); nunca en claro.
- Sesión del portal con claves propias (`portal_employee_id`,
  `portal_employee_code`, `portal_employee_name`) — independiente de la sesión
  admin (`user_id`). El login del portal hace `session.clear()` antes de
  fijarlas (rotación de sesión).
- Rate limit: **5 intentos fallidos / 15 min** por `employee_code`.
- Anti-enumeración: un único mensaje genérico para código desconocido, empleado
  inactivo, empleado sin PIN y PIN incorrecto.

## Gestión del PIN (RRHH/admin)

En el expediente del colaborador (`/colaboradores/expediente/<id>`, solo
`admin_required`):

- `POST /colaboradores/expediente/<id>/pin/generar` — genera PIN aleatorio de
  6 dígitos, lo hashea y lo muestra **una sola vez** vía flash.
- `POST /colaboradores/expediente/<id>/pin/limpiar` — elimina el PIN
  (bloquea el acceso al portal).

## Rutas

| Ruta | Descripción |
|---|---|
| `GET/POST /mi-asistencia/login` | Login con employee_code + PIN |
| `GET /mi-asistencia/logout` | Cierra la sesión del portal |
| `GET /mi-asistencia` | Vista HTML: resumen del periodo + tabla de marcas propias |
| `GET /mi-asistencia/api/records` | JSON de marcas propias (`start_date`, `end_date`) |
| `GET /mi-asistencia/aviso-privacidad` | Aviso de privacidad (datos biometricos = sensibles LFPDPPP) |

## Aislamiento (criterio de aceptación)

- Todas las consultas filtran **solo** por los pares `(device_ip, user_id)`
  obtenidos de `employee_device_links` del empleado de la sesión.
- Cualquier query param `employee_id` distinto del propio responde **403**
  (página HTML en la vista, JSON en la API). No existe ruta que acepte ver
  registros ajenos.
- Sin sesión del portal: redirect a login (HTML) / 401 (JSON).

## Cómputo del periodo

- Rango: `start_date`/`end_date` ISO (default: mes en curso). Máximo **92
  días**, `end_date` no futura.
- `worked`: por día con ≥ 2 marcas, `última marca - primera marca`.
- `extra`: `max(0, worked - 8h)` por día (LFT 61/66, jornada diurna 8 h). El
  motor de reglas completo es MYK-224.
- `late`: primer entrada (status=0) posterior a `ATTENDANCE_WORK_START`
  (default 09:00:00, mismo criterio que `attendance_stats` MYK-241).
- Las marcas se listan con su tipo (`Entrada`, `Salida`, …) según `status`
  del reloj.

## Privacidad

El aviso (`/mi-asistencia/aviso-privacidad`) enlazado desde el login y la vista:
responsable, datos tratados (plantilla biométrica vive solo en el dispositivo),
finalidades, conservación (LFT 804-III) y derechos ARCO.

## Tests

`tests/test_mi_asistencia.py` — e2e con `webgui_app`: login/rate limit, aislamiento
(403 ajeno, HTML sin datos de otros), API de registros, cómputo de extra/retardos,
gestión de PIN por admin y aviso de privacidad.
