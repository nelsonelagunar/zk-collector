FROM python:3.12-slim AS base

LABEL org.opencontainers.image.source="https://github.com/nelsonelagunar/zk-collector"
LABEL org.opencontainers.image.description="ZKTeco attendance device collector + web dashboard"

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    supervisor \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Copy entrypoint script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Copy supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create log directory
RUN mkdir -p /app/logs && chmod 755 /app/logs

# Runtime
ENV ZK_COLLECTOR_HOST=0.0.0.0
ENV ZK_COLLECTOR_PORT=8080
ENV ZK_COLLECTOR_DATA=/app/data

VOLUME /app/data
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]