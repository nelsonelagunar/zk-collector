#!/bin/sh
# ZK-Collector Docker Entrypoint
# Validates required environment variables before starting the application

set -e

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