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

---

#### Logout

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/logout` | Destroy session |

```bash
curl -b cookies.txt -X POST http://localhost:8080/auth/logout
```

---

#### Initial Setup (First Run)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/auth/setup` | Create first admin user |

```bash
curl -c cookies.txt -X POST http://localhost:8080/auth/setup \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secure-password&confirm=secure-password"
```

---

### Devices

#### List All Devices

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/devices/api/devices` | Get all configured devices |

```bash
curl -b cookies.txt http://localhost:8080/devices/api/devices
```

**Response (200 OK):**
```json
{
  "devices": [
    {
      "id": 1,
      "name": "Entrada Principal",
      "location": "Main Entrance",
      "zone": "Zone A",
      "address": "192.168.1.101",
      "port": 4370,
      "password": 0,
      "timeout": 5,
      "protocol": "tcp",
      "status": "online",
      "enabled": true,
      "firmware_version": "1.2.3",
      "serial_number": "ZK123456",
      "last_seen": "2025-01-15T10:30:00",
      "created_at": "2025-01-10T08:00:00",
      "updated_at": "2025-01-15T10:30:00"
    }
  ]
}
```

---

#### Create Device

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/devices/api/devices` | Add a new ZKTeco device |

```bash
curl -b cookies.txt -X POST http://localhost:8080/devices/api/devices \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Entrada Principal",
    "location": "Main Entrance",
    "zone": "Zone A",
    "address": "192.168.1.101",
    "port": 4370,
    "password": 0,
    "timeout": 5,
    "protocol": "tcp"
  }'
```

**Request Schema:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | ✅ | — | Human-readable name |
| `location` | string | ❌ | "" | Physical location |
| `zone` | string | ❌ | "" | Logical zone/group |
| `address` | string | ✅ | — | Device IP address |
| `port` | integer | ❌ | 4370 | TCP/UDP port |
| `password` | integer | ❌ | 0 | Device comm password |
| `timeout` | integer | ❌ | 5 | Connection timeout (seconds) |
| `protocol` | string | ❌ | "tcp" | "tcp" or "udp" |

**Response (201 Created):**
```json
{
  "success": true,
  "device_id": 1,
  "message": "Device created successfully"
}
```

---

#### Get Device by ID

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/devices/api/devices/{id}` | Get single device details |

```bash
curl -b cookies.txt http://localhost:8080/devices/api/devices/1
```

**Response (200 OK):**
```json
{
  "id": 1,
  "name": "Entrada Principal",
  "location": "Main Entrance",
  "zone": "Zone A",
  "address": "192.168.1.101",
  "port": 4370,
  "password": 0,
  "timeout": 5,
  "protocol": "tcp",
  "status": "online",
  "enabled": true,
  "firmware_version": "1.2.3",
  "serial_number": "ZK123456",
  "last_seen": "2025-01-15T10:30:00",
  "created_at": "2025-01-10T08:00:00",
  "updated_at": "2025-01-15T10:30:00"
}
```

---

#### Update Device

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/devices/api/devices/{id}` | Update device configuration |

```bash
curl -b cookies.txt -X PUT http://localhost:8080/devices/api/devices/1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Entrada Principal Updated",
    "location": "Main Entrance - Lobby",
    "address": "192.168.1.101",
    "port": 4370,
    "password": 0,
    "timeout": 10,
    "protocol": "tcp"
  }'
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Device updated successfully"
}
```

---

#### Delete Device

| Method | Endpoint | Description |
|--------|----------|-------------|
| `DELETE` | `/devices/api/devices/{id}` | Remove a device |

```bash
curl -b cookies.txt -X DELETE http://localhost:8080/devices/api/devices/1
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Device deleted successfully"
}
```

---

#### Test Device Connection

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/devices/api/devices/test` | Test connection to a device (by IP) |

```bash
curl -b cookies.txt -X POST http://localhost:8080/devices/api/devices/test \
  -H "Content-Type: application/json" \
  -d '{
    "address": "192.168.1.101",
    "port": 4370,
    "password": 0,
    "timeout": 5,
    "protocol": "tcp"
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

**Response (400 Bad Request - Connection Failed):**
```json
{
  "success": false,
  "message": "Connection timeout"
}
```

---

#### Toggle Device Enabled State

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/devices/api/devices/{id}/toggle` | Enable/disable device polling |

```bash
curl -b cookies.txt -X POST http://localhost:8080/devices/api/devices/1/toggle
```

**Response (200 OK):**
```json
{
  "success": true,
  "enabled": false,
  "message": "Device disabled"
}
```

---

#### Get Device Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/devices/api/devices/{id}/status` | Get real-time device status |

```bash
curl -b cookies.txt http://localhost:8080/devices/api/devices/1/status
```

**Response (200 OK):**
```json
{
  "id": 1,
  "status": "online",
  "last_seen": "2025-01-15T10:30:00",
  "firmware_version": "1.2.3",
  "serial_number": "ZK123456",
  "record_count": 1250
}
```

---

### Attendance Records

#### List Attendance Records

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/devices/api/attendance` | Get attendance records with filters |

```bash
# Get recent records
curl -b cookies.txt "http://localhost:8080/devices/api/attendance?limit=50&offset=0"

# Filter by device
curl -b cookies.txt "http://localhost:8080/devices/api/attendance?device_id=1&limit=100"

# Filter by date range
curl -b cookies.txt "http://localhost:8080/devices/api/attendance?date_from=2025-01-01&date_to=2025-01-31"

# Filter by user
curl -b cookies.txt "http://localhost:8080/devices/api/attendance?user_id=12345"
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `device_id` | integer | Filter by device ID |
| `user_id` | string | Filter by user ID |
| `date_from` | string | Start date (YYYY-MM-DD) |
| `date_to` | string | End date (YYYY-MM-DD) |
| `limit` | integer | Max records (default: 50, max: 1000) |
| `offset` | integer | Pagination offset (default: 0) |
| `synced` | boolean | Filter by sync status (true/false) |

**Response (200 OK):**
```json
{
  "records": [
    {
      "id": 1,
      "device_id": 1,
      "device_name": "Entrada Principal",
      "user_id": "12345",
      "timestamp": "2025-01-15T08:30:00",
      "punch_type": "check_in",
      "verified": true,
      "synced": true,
      "created_at": "2025-01-15T08:30:05"
    }
  ],
  "total": 1250,
  "limit": 50,
  "offset": 0
}
```

**Punch Types:**
- `check_in` — Employee check-in
- `check_out` — Employee check-out
- `break_out` — Break start
- `break_in` — Break end
- `overtime_in` — Overtime start
- `overtime_out` — Overtime end

---

#### Get Attendance Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/devices/api/attendance/stats` | Get attendance summary statistics |

```bash
curl -b cookies.txt "http://localhost:8080/devices/api/attendance/stats?date_from=2025-01-01&date_to=2025-01-31"
```

**Response (200 OK):**
```json
{
  "total_records": 1250,
  "unique_users": 45,
  "devices_active": 3,
  "by_punch_type": {
    "check_in": 620,
    "check_out": 600,
    "break_out": 15,
    "break_in": 15
  },
  "by_device": [
    {
      "device_id": 1,
      "device_name": "Entrada Principal",
      "count": 500
    }
  ],
  "date_range": {
    "from": "2025-01-01",
    "to": "2025-01-31"
  }
}
```

---

#### Export Attendance (CSV)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/devices/api/attendance/export` | Export attendance records as CSV |

```bash
curl -b cookies.txt "http://localhost:8080/devices/api/attendance/export?date_from=2025-01-01&date_to=2025-01-31" \
  -o attendance-jan-2025.csv
```

**Response:** CSV file download with columns: `id, device_id, device_name, user_id, timestamp, punch_type, verified, synced, created_at`

---

### Platform Sync

#### Sync Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/devices/api/sync/status` | Get cloud sync status |

```bash
curl -b cookies.txt http://localhost:8080/devices/api/sync/status
```

**Response (200 OK):**
```json
{
  "enabled": true,
  "platform_url": "https://api.example.com",
  "tenant_id": "tenant-123",
  "last_sync": "2025-01-15T10:25:00",
  "pending_records": 12,
  "last_error": null,
  "sync_interval_seconds": 60
}
```

---

#### Trigger Manual Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/devices/api/sync/trigger` | Force immediate sync to platform |

```bash
curl -b cookies.txt -X POST http://localhost:8080/devices/api/sync/trigger
```

**Response (200 OK):**
```json
{
  "success": true,
  "synced_count": 12,
  "message": "Sync completed successfully"
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable error description"
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

---

## Rate Limits

| Endpoint Category | Limit |
|-------------------|-------|
| Device CRUD | 60 requests/minute |
| Attendance queries | 30 requests/minute |
| Sync operations | 10 requests/minute |
| Health check | No limit |

---

## Complete Example: Add Device & Verify

```bash
#!/bin/bash
# Full workflow: login → add device → test → list

COLLECTOR="http://localhost:8080"
COOKIES="cookies.txt"

# 1. Login
curl -c "$COOKIES" -s -X POST "$COLLECTOR/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=changeme" > /dev/null

# 2. Add device
DEVICE_RESPONSE=$(curl -b "$COOKIES" -s -X POST "$COLLECTOR/devices/api/devices" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "K40 Reception",
    "location": "Building A - Reception",
    "address": "192.168.1.101",
    "port": 4370,
    "password": 0
  }')

DEVICE_ID=$(echo "$DEVICE_RESPONSE" | jq -r '.device_id')
echo "Created device ID: $DEVICE_ID"

# 3. Test connection
curl -b "$COOKIES" -s -X POST "$COLLECTOR/devices/api/devices/test" \
  -H "Content-Type: application/json" \
  -d "{
    \"address\": \"192.168.1.101\",
    \"port\": 4370,
    \"password\": 0
  }" | jq .

# 4. List devices
curl -b "$COOKIES" -s "$COLLECTOR/devices/api/devices" | jq .

# 5. Get attendance for last 7 days
curl -b "$COOKIES" -s "$COLLECTOR/devices/api/attendance?date_from=$(date -d '7 days ago' +%F)&limit=100" | jq .
```

---

## OpenAPI / Swagger

The API is documented in OpenAPI 3.1 format. Download the spec:

```bash
curl http://localhost:8080/openapi.json -o openapi.json
```

View in Swagger UI: `http://localhost:8080/docs` (when enabled in config)
