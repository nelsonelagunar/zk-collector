# API Reference

ZK-Collector exposes a REST API for device management, attendance data, and system health. The web dashboard consumes this same API.

## Base URL

```
http://<collector-host>:8080
```

## Authentication

All API endpoints (except `/health`) require authentication via session cookie. Obtain a session by logging in through `/auth/login`.

```bash
# Login to get session cookie
curl -c cookies.txt -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your-password"

# Use cookie for subsequent requests
curl -b cookies.txt http://localhost:8080/devices/api/devices
```

---

## Endpoints

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check (no auth required) |

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

### Authentication

#### Login

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | Authenticate and create session |

**Request:**
```bash
curl -c cookies.txt -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your-password"
```

**Response (200 OK):** Redirects to `/` with session cookie set.

#### Logout

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/auth/logout` | Destroy session |

```bash
curl -b cookies.txt -X POST http://localhost:8080/auth/logout
```

#### Initial Setup (First Run)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/auth/setup` | Create first admin user |

```bash
curl -c cookies.txt -X POST http://localhost:8080/auth/setup \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secure-password&confirm=secure-password"
```

#### Password Recovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/auth/forgot-password` | Show password recovery form |
| `POST` | `/auth/forgot-password` | Request password recovery email |

```bash
curl -c cookies.txt -X POST http://localhost:8080/auth/forgot-password \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=user@example.com"
```

---

### Device Connectivity Test

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/devices/api/devices/test` | Test connection to a device by IP (no config saved) |

**Request:**
```bash
curl -b cookies.txt -X POST http://localhost:8080/devices/api/devices/test \
  -H "Content-Type: application/json" \
  -d '{
    "address": "192.168.1.101",
    "port": 4370,
    "password": 0,
    "protocol": "tcp",
    "timeout": 5
  }'
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Connection successful",
  "device_info": {
    "firmware": "1.2.3",
    "serial": "ZK123456",
    "platform": "ZKFW"
  }
}
```

**Response (400 Bad Request - Invalid input):**
```json
{
  "error": "Validation error"
}
```

**Response (502 Bad Gateway - Connection Failed):**
```json
{
  "success": false,
  "message": "Connection timeout"
}
```

---

### API Documentation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/docs` | Interactive Swagger UI |
| `GET` | `/api/openapi.yaml` | OpenAPI 3.1 spec (YAML) |
| `GET` | `/api/openapi.json` | OpenAPI 3.1 spec (JSON) |

```bash
# Get OpenAPI spec as YAML
curl http://localhost:8080/api/openapi.yaml -o openapi.yaml

# Get OpenAPI spec as JSON
curl http://localhost:8080/api/openapi.json -o openapi.json
```

View in Swagger UI: `http://localhost:8080/api/docs`

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Human-readable error description"
}
```

**Common HTTP Status Codes:**
| Code | Meaning |
|------|---------|
| `400` | Bad Request - invalid input |
| `401` | Unauthorized - session expired |
| `403` | Forbidden - insufficient permissions |
| `404` | Not Found |
| `500` | Internal Server Error |
| `502` | Bad Gateway - device unreachable |
| `503` | Service Unavailable - platform unreachable |

---

## Rate Limits

| Endpoint Category | Limit |
|-------------------|-------|
| Auth endpoints | 60 requests/minute |
| Device test endpoint | 30 requests/minute |
| API documentation | No limit |
| Health check | No limit |

---

## Complete Example: Test Device Connection

```bash
#!/bin/bash
# Full workflow: login → test device

COLLECTOR="http://localhost:8080"
COOKIES="cookies.txt"

# 1. Login
curl -c "$COOKIES" -s -X POST "$COLLECTOR/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=changeme" > /dev/null

# 2. Test device connection
curl -b "$COOKIES" -s -X POST "$COLLECTOR/devices/api/devices/test" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "192.168.1.101",
    "port": 4370,
    "password": 0,
    "protocol": "tcp",
    "timeout": 5
  }' | jq .
```