# MCP Server — zk-collector

ZK-Collector ships an optional **MCP (Model Context Protocol) server** so AI agents
can query attendance data through the same REST/JSON endpoints the dashboard
uses. It is **read-only** and **token-authenticated**: the agent never sees
credentials, only API responses.

```
AI agent ──MCP (stdio o HTTP)──▶ zk-collector-mcp ──HTTP + Bearer──▶ WebGUI API (8080)
```

## Requisitos

- Python 3.12+
- Un zk-collector accesible por HTTP (local o LAN)
- Un **personal access token** creado en la WebGUI (ver [Seguridad](#seguridad))

```bash
pip install "zk-collector[mcp]"
```

El extra instala el SDK oficial `mcp` y el comando `zk-collector-mcp`.

## Configuración (variables de entorno)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ZK_COLLECTOR_URL` | `http://127.0.0.1:8080` | Base URL de la WebGUI (http/https). |
| `ZK_COLLECTOR_API_TOKEN` | (requerido) | Personal access token. Alternativa: `ZK_API_TOKEN`. |
| `ZK_COLLECTOR_MCP_TIMEOUT` | `10` | Timeout HTTP en segundos (1-60). |
| `ZK_COLLECTOR_MCP_HTTP` | `0` | `1` activa el transporte HTTP streamable en vez de stdio. |
| `ZK_COLLECTOR_MCP_HOST` | `127.0.0.1` | Bind del modo HTTP. **No** usar `0.0.0.0` salgo detrás de un proxy con TLS. |
| `ZK_COLLECTOR_MCP_PORT` | `9248` | Puerto del modo HTTP. |

Sin token configurado el server arranca con exit code 2 y un mensaje claro en
stderr: nunca funciona "abierto".

## Setup con un cliente MCP (stdio, recomendado)

Con transporte stdio el cliente MCP (Claude Desktop, Claude Code, otros)
lanza el proceso localmente — **no se abre ningún puerto**.

Ejemplo para Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "zk-collector": {
      "command": "zk-collector-mcp",
      "env": {
        "ZK_COLLECTOR_URL": "http://192.168.1.50:8080",
        "ZK_COLLECTOR_API_TOKEN": "<tu-personal-access-token>"
      }
    }
  }
}
```

Con cualquier cliente genérico, el comando es el mismo:

```bash
ZK_COLLECTOR_URL=http://192.168.1.50:8080 \
ZK_COLLECTOR_API_TOKEN=<tu-token> \
zk-collector-mcp
```

## Setup HTTP (opt-in, solo localhost)

```bash
ZK_COLLECTOR_API_TOKEN=<tu-token> \
ZK_COLLECTOR_MCP_HTTP=1 \
ZK_COLLECTOR_MCP_PORT=9248 \
zk-collector-mcp
```

Queda escuchando en `http://127.0.0.1:9248/mcp`. Si necesitas acceso remoto,
ponlo detrás de un reverse proxy con TLS y autenticación adicional — nunca
expongas este puerto a internet.

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
      - ZK_COLLECTOR_API_TOKEN=${ZK_MCP_TOKEN}
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

- **Token:** el server lee el token de `ZK_COLLECTOR_API_TOKEN` una vez al
  arrancar, lo envía como `Authorization: Bearer` en cada request y **nunca**
  lo loguea, lo devuelve en tools ni lo incluye en mensajes de error (los
  detalles de respuesta se sanitizan). Crea el token en la WebGUI con el
  scope mínimo de lectura y revócalo ahí si se compromete.
- **Read-only:** las 4 tools solo hacen `GET`. El server no expone ninguna
  operación de escritura sobre dispositivos ni datos.
- **Red:** stdio no abre puertos; el modo HTTP bindea `127.0.0.1` por defecto.
  El puerto 4370 del protocolo ZK nunca se abre ni se proxya por este server.
- **Timeouts/retries:** cada request HTTP tiene timeout configurable (10s por
  defecto) y un solo reintento en errores de conexión; los errores HTTP
  (401/404/5xx) se reportan al agente con mensajes seguros, sin reintento.

## Desarrollo

```bash
pip install -e ".[dev]"        # incluye mcp
pytest tests/test_mcp_server.py -v
```

Los tests cubren configuración, cliente HTTP, mapeo de tools, registro en
FastMCP y un handshake end-to-end contra la app Flask real (`create_app`).
