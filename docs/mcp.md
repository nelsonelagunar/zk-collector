# MCP Server — zk-collector

ZK-Collector ships an optional **MCP (Model Context Protocol) server** so AI agents
can query attendance data through the same REST/JSON endpoints the dashboard
uses. It is **read-only** and **JWT-authenticated**: the agent never sees
credentials, only API responses.

```
AI agent ──MCP (stdio o HTTP)──▶ zk-collector-mcp ──HTTP + Bearer──▶ WebGUI API (8080)
```

## Requisitos

- Python 3.12+
- Un zk-collector accesible por HTTP (local o LAN)
- Una **credencial** (ver [Seguridad](#seguridad)): un access JWT de la WebGUI
  o el secreto HS256 compartido para que el server mintee los suyos

```bash
pip install "zk-collector[mcp]"
```

El extra instala el SDK oficial `mcp` y el comando `zk-collector-mcp`.

## Autenticación (dos modos, exactamente uno al arrancar)

La WebGUI **no tiene** UI de personal access tokens: su API valida
`Authorization: Bearer` como **JWT HS256** (`type=access`, 30 min de vida,
firmado con `WEBGUI_SECRET_KEY` — `src/webgui/auth.py`, MYK-443). El MCP server
soporta dos modos:

| Modo | Variable | Comportamiento |
|------|----------|----------------|
| `static` | `ZK_COLLECTOR_API_TOKEN` (o `ZK_API_TOKEN`) | JWT ya emitido que se envía tal cual. Expira: renuévalo tú. |
| `minted` **(recomendado)** | `ZK_COLLECTOR_JWT_SECRET` (o `WEBGUI_SECRET_KEY`) | El server mintea sus propios access JWT con el rol elegido, los cachea y los **auto-refresca** antes de expirar y una vez por request ante un 401. |

Para el modo `static`, mintea un JWT externo (no hay endpoint de emisión; el
login solo crea sesión):

```bash
python -c "from src.webgui.auth import Auth; print(Auth('TU_WEBGUI_SECRET_KEY').generate_tokens(user_id=1, username='mcp', role='supervisor')['access_token'])"
```

## Configuración (variables de entorno)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ZK_COLLECTOR_URL` | `http://127.0.0.1:8080` | Base URL de la WebGUI (http/https). |
| `ZK_COLLECTOR_API_TOKEN` | — | Modo `static`: access JWT. Alternativa: `ZK_API_TOKEN`. Tiene precedencia sobre el secret. |
| `ZK_COLLECTOR_JWT_SECRET` | — | Modo `minted`: secreto HS256 compartido con la WebGUI. Fallback: `WEBGUI_SECRET_KEY`. |
| `ZK_COLLECTOR_MCP_TOKEN_ROLE` | `supervisor` | Rol del claim para los JWT minteados. |
| `ZK_COLLECTOR_MCP_TOKEN_TTL_MINUTES` | `30` | Vida de cada JWT minteado (1-1440). |
| `ZK_COLLECTOR_MCP_TIMEOUT` | `10` | Timeout HTTP en segundos (1-60). |
| `ZK_COLLECTOR_MCP_HTTP` | `0` | `1` activa el transporte HTTP streamable en vez de stdio. |
| `ZK_COLLECTOR_MCP_HOST` | `127.0.0.1` | Bind del modo HTTP. Solo loopback salvo `ZK_COLLECTOR_MCP_ALLOW_REMOTE_BIND=1`. |
| `ZK_COLLECTOR_MCP_ALLOW_REMOTE_BIND` | `0` | `1` permite bind no-loopback (tras un reverse proxy con TLS). |
| `ZK_COLLECTOR_MCP_PORT` | `9248` | Puerto del modo HTTP. |

Sin credencial configurada el server arranca con exit code 2 y un mensaje claro
en stderr: nunca funciona "abierto".

## Setup con un cliente MCP (stdio, recomendado)

Con transporte stdio el cliente MCP (Claude Desktop, Claude Code, otros)
lanza el proceso localmente — **no se abre ningún puerto**.

Ejemplo para Claude Desktop (`claude_desktop_config.json`), modo `minted`:

```json
{
  "mcpServers": {
    "zk-collector": {
      "command": "zk-collector-mcp",
      "env": {
        "ZK_COLLECTOR_URL": "http://192.168.1.50:8080",
        "ZK_COLLECTOR_JWT_SECRET": "<secreto-hs256-de-la-webgui>"
      }
    }
  }
}
```

Con cualquier cliente genérico, el comando es el mismo:

```bash
ZK_COLLECTOR_URL=http://192.168.1.50:8080 \
ZK_COLLECTOR_JWT_SECRET=<secreto-hs256-de-la-webgui> \
zk-collector-mcp
```

Modo `static` (JWT minteado externo, expira en 30 min):

```bash
ZK_COLLECTOR_URL=http://192.168.1.50:8080 \
ZK_COLLECTOR_API_TOKEN=<access-jwt> \
zk-collector-mcp
```

## Setup HTTP (opt-in, solo localhost)

```bash
ZK_COLLECTOR_JWT_SECRET=<secreto-hs256-de-la-webgui> \
ZK_COLLECTOR_MCP_HTTP=1 \
ZK_COLLECTOR_MCP_PORT=9248 \
zk-collector-mcp
```

Queda escuchando en `http://127.0.0.1:9248/mcp`. Los binds no-loopback se
rechazan al arrancar salvo `ZK_COLLECTOR_MCP_ALLOW_REMOTE_BIND=1`; si necesitas
acceso remoto, ponlo detrás de un reverse proxy con TLS y autenticación
adicional — nunca expongas este puerto a internet.

## Docker (opt-in)

El server **no** corre dentro del contenedor del collector por defecto.

- **stdio:** instala `zk-collector[mcp]` en el host donde corre el cliente MCP
  y apunta `ZK_COLLECTOR_URL` al contenedor (`http://<host>:8080`). No toca la
  red del contenedor.
- **HTTP:** levanta un segundo contenedor solo de MCP y publica el puerto
  **solo hacia localhost**:

```yaml
  zk-mcp:
    build: .
    entrypoint: ["zk-collector-mcp"]
    command: []
    environment:
      - ZK_COLLECTOR_URL=http://zk-collector:8080
      - ZK_COLLECTOR_JWT_SECRET=${ZK_MCP_JWT_SECRET}
      - ZK_COLLECTOR_MCP_HTTP=1
    ports:
      - "127.0.0.1:9248:9248"   # localhost-only
    depends_on:
      - zk-collector
```

El puerto 4370 (protocolo ZK) y la WebGUI no se ven afectados: el server MCP
es un cliente HTTP más de la API.

## Tools (read-only)

| Tool | Endpoint | Descripción |
|------|----------|-------------|
| `attendance_stats` | `GET /api/attendance/stats` | KPIs de asistencia (presentes, ausencias, retardos, puntualidad) con filtros de fecha/empleado/departamento y `group_by`. |
| `list_punches` | `GET /attendance/api/attendance` | Checadas crudas del buffer, paginadas, filtros fecha/usuario/dispositivo. |
| `list_devices` | `GET /attendance/api/devices` | Dispositivos habilitados (id, nombre, IP). |
| `list_employees` | `GET /api/employees/` | Registro de colaboradores, paginado, con filtros status/departamento/búsqueda. |

## Seguridad

- **Credenciales:** el server lee la credencial una vez al arrancar y la envía
  como `Authorization: Bearer` en cada request. En modo `minted` refresca el
  JWT antes de expirar y **re-mintea una única vez por request** si recibe 401.
  El secret y cada token son privados al proceso: **nunca** se loguean, se
  devuelven en tools ni se incluyen en mensajes de error (los detalles de
  respuesta se sanitizan contra la lista de valores sensibles).
- **Rotación:** modo `minted` = rota `WEBGUI_SECRET_KEY`/`ZK_COLLECTOR_JWT_SECRET`
  del server MCP. Modo `static` = deja de pasar el JWT y este expira solo (30 min).
- **Read-only:** las 4 tools solo hacen `GET`. El server no expone ninguna
  operación de escritura sobre dispositivos ni datos.
- **Red:** stdio no abre puertos; el modo HTTP bindea `127.0.0.1` por defecto y
  rechaza binds no-loopback sin override explícito. El puerto 4370 del
  protocolo ZK nunca se abre ni se proxya por este server.
- **Timeouts/retries:** cada request HTTP tiene timeout configurable (10s por
  defecto) y un solo reintento en errores de conexión; los errores HTTP
  (404/5xx) se reportan al agente con mensajes seguros, sin reintento. El 401
  es la única excepción: con credencial `minted` re-mintea y reintenta una vez
  antes de reportarlo.

## Desarrollo

```bash
pip install -e ".[dev]"        # incluye mcp
pytest tests/test_mcp_server.py -v
```

Los tests cubren configuración, cliente HTTP, mapeo de tools, registro en
FastMCP y handshakes end-to-end contra la app Flask real (`create_app`) en
ambos modos, incluido el rechazo 401 de credenciales inválidas.
