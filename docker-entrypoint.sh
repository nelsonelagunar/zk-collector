#!/bin/sh
# ZK-Collector Docker Entrypoint
# Validates required environment variables before starting the application
# Bootstraps the WebGUI SQLite schema, the admin user and (one-shot) migrates
# devices from collector.yaml to the WebGUI DB.

set -e

WEBGUI_DB_PATH="${WEBGUI_DB_PATH:-/app/data/webgui.db}"
COLLECTOR_CONFIG_PATH="${COLLECTOR_CONFIG_PATH:-/app/configs/collector.yaml}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@localhost}"

echo "=== ZK-Collector Startup ==="
echo "Validating environment variables..."

# Required environment variables
REQUIRED_VARS="
    ZK_ADMIN_PASSWORD
    ENCRYPTION_KEY
"

# Optional but recommended for production
OPTIONAL_VARS="
    ZK_SYNC_URL
    ZK_SYNC_TOKEN
    WEBGUI_SECRET_KEY
    LOG_LEVEL
    LOG_FORMAT
"

# SMTP Configuration (for password reset emails)
SMTP_VARS="
    SMTP_HOST
    SMTP_PORT
    SMTP_USERNAME
    SMTP_PASSWORD
    SMTP_FROM_EMAIL
    SMTP_USE_TLS
"

MISSING_VARS=""

for var in $REQUIRED_VARS; do
    eval value=\$$var
    if [ -z "$value" ]; then
        MISSING_VARS="$MISSING_VARS $var"
        echo "  ❌ MISSING REQUIRED: $var"
    else
        echo "  ✓ $var is set"
    fi
done

for var in $OPTIONAL_VARS; do
    eval value=\$$var
    if [ -z "$value" ]; then
        echo "  ⚠ OPTIONAL (not set): $var"
    else
        echo "  ✓ $var is set"
    fi
done

# Check SMTP configuration
echo "Checking SMTP configuration..."
SMTP_CONFIGURED=true
for var in $SMTP_VARS; do
    eval value=\$$var
    if [ -z "$value" ]; then
        SMTP_CONFIGURED=false
        echo "  ⚠ SMTP (not set): $var"
    else
        echo "  ✓ SMTP $var is set"
    fi
done

if [ -n "$MISSING_VARS" ]; then
    echo ""
    echo "ERROR: The following required environment variables are not set:"
    for var in $MISSING_VARS; do
        echo "  - $var"
    done
    echo ""
    echo "Please set them in your .env file or environment."
    echo "Example: cp .env.example .env && nano .env"
    exit 1
fi

echo ""
echo "Environment validation passed!"

# ---------------------------------------------------------------------------
# Bootstrap the WebGUI schema (idempotent). The server applies migrations on
# import too, but doing it here guarantees the schema exists before the SMTP
# and device migrations below run on a fresh container.
# ---------------------------------------------------------------------------
ensure_webgui_schema() {
    echo "Ensuring WebGUI database schema..."
    mkdir -p "$(dirname "$WEBGUI_DB_PATH")"
    ( cd /app && DB_PATH="$WEBGUI_DB_PATH" python3 - <<'PY'
import os
from pathlib import Path

from src.webgui.database import Database

db_path = Path(os.environ["DB_PATH"])
Database(db_path).initialize()
print(f"  schema ready: {db_path}")
PY
    ) && echo "  Schema OK" || echo "  ⚠ Schema initialization failed"
}

# ---------------------------------------------------------------------------
# Provision the admin user from ZK_ADMIN_PASSWORD when the users table is
# empty, so a freshly deployed container is usable without the setup wizard.
# ---------------------------------------------------------------------------
ensure_admin_user() {
    if [ -z "$ZK_ADMIN_PASSWORD" ]; then
        echo "  ZK_ADMIN_PASSWORD not set (skipping admin provisioning)"
        return 0
    fi
    echo "Ensuring admin user..."
    ( cd /app && \
      DB_PATH="$WEBGUI_DB_PATH" \
      ADMIN_USERNAME="$ADMIN_USERNAME" \
      ADMIN_EMAIL="$ADMIN_EMAIL" \
      ZK_ADMIN_PASSWORD="$ZK_ADMIN_PASSWORD" \
      python3 - <<'PY'
import os
import sqlite3

from src.webgui.auth import Auth

db_path = os.environ["DB_PATH"]
username = os.environ.get("ADMIN_USERNAME", "admin")
email = os.environ.get("ADMIN_EMAIL", "")
password = os.environ["ZK_ADMIN_PASSWORD"]

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
if count == 0:
    password_hash = Auth("bootstrap").hash_password(password)
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role, is_active) "
        "VALUES (?, ?, ?, 'admin', 1)",
        (username, email, password_hash),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO system_config (key, value, description) "
        "VALUES ('setup_completed', 'true', 'setup')"
    )
    conn.commit()
    print(f"  admin user '{username}' created")
else:
    print(f"  {count} user(s) already exist (skipping admin provisioning)")
conn.close()
PY
    ) && echo "  Admin OK" || echo "  ⚠ Admin provisioning failed"
}

ensure_webgui_schema
ensure_admin_user

if [ "$SMTP_CONFIGURED" = "true" ]; then
    echo "Writing SMTP configuration to system_config..."
    sqlite3 "$WEBGUI_DB_PATH" "
        UPDATE system_config SET value = '$SMTP_HOST' WHERE key = 'smtp_host';
        UPDATE system_config SET value = '$SMTP_PORT' WHERE key = 'smtp_port';
        UPDATE system_config SET value = '$SMTP_USERNAME' WHERE key = 'smtp_username';
        UPDATE system_config SET value = '$SMTP_PASSWORD' WHERE key = 'smtp_password';
        UPDATE system_config SET value = '$SMTP_FROM_EMAIL' WHERE key = 'smtp_from_email';
        UPDATE system_config SET value = '$SMTP_USE_TLS' WHERE key = 'smtp_use_tls';
        UPDATE system_config SET value = 'true' WHERE key = 'smtp_configured';
    " 2>/dev/null && echo "  SMTP configuration written to DB" || echo "  ⚠ Failed to write SMTP config to DB"
else
    echo "  SMTP not fully configured - password reset will show token in UI (dev mode)"
fi

migrate_devices_from_yaml_to_webgui_db() {
    echo "Checking for one-shot YAML to DB migration..."

    if [ ! -f "$COLLECTOR_CONFIG_PATH" ]; then
        echo "  Config file not found: $COLLECTOR_CONFIG_PATH (skipping migration)"
        return 0
    fi

    if [ ! -f "$WEBGUI_DB_PATH" ]; then
        echo "  WebGUI DB not found: $WEBGUI_DB_PATH (skipping migration)"
        return 0
    fi

    DEVICE_COUNT=$(python3 -c "
import sqlite3
conn = sqlite3.connect('$WEBGUI_DB_PATH')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM devices;')
count = cursor.fetchone()[0]
conn.close()
print(count)
" 2>/dev/null || echo "0")
    if [ "$DEVICE_COUNT" -gt 0 ]; then
        echo "  WebGUI DB already has $DEVICE_COUNT device(s) (skipping migration, preserving source of truth)"
        return 0
    fi

    echo "  Found empty devices table, checking collector.yaml for devices..."

    python3 -c "
import sys
import yaml
import sqlite3

config_path = '$COLLECTOR_CONFIG_PATH'
db_path = '$WEBGUI_DB_PATH'

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

devices = config.get('devices', [])
if not devices:
    print('  No devices section found in collector.yaml (skipping migration)')
    sys.exit(0)

enabled_devices = [d for d in devices if d.get('enabled', False) is True]
if not enabled_devices:
    print('  No enabled devices found in collector.yaml (skipping migration)')
    sys.exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

migrated = 0
for device in enabled_devices:
    name = device.get('name', 'Unknown')
    ip = device.get('ip', '')
    port = device.get('port', 4370)
    password = device.get('password', '0')
    timeout = device.get('timeout', 5)
    
    if not ip:
        continue
    
    cursor.execute('''
        INSERT INTO devices (name, address, port, password, timeout, is_enabled, status)
        VALUES (?, ?, ?, ?, ?, 1, 'unknown')
    ''', (name, ip, port, password, timeout))
    migrated += 1

conn.commit()
conn.close()
print(f'  Migrated {migrated} devices from collector.yaml to WebGUI DB')
"
    if [ $? -eq 0 ]; then
        echo "  Migration completed successfully"
    else
        echo "  Migration failed or was skipped"
    fi
}

migrate_devices_from_yaml_to_webgui_db

# Export all env vars for supervisord
export ENV_ZK_ADMIN_PASSWORD="${ZK_ADMIN_PASSWORD}"
export ENV_ENCRYPTION_KEY="${ENCRYPTION_KEY}"
export ENV_ZK_SYNC_URL="${ZK_SYNC_URL}"
export ENV_ZK_SYNC_TOKEN="${ZK_SYNC_TOKEN}"
export ENV_WEBGUI_SECRET_KEY="${WEBGUI_SECRET_KEY}"
export ENV_LOG_LEVEL="${LOG_LEVEL:-INFO}"
export ENV_LOG_FORMAT="${LOG_FORMAT:-text}"

echo "Starting ZK-Collector with supervisord..."
echo ""

# Execute the main command (supervisord)
exec "$@"
