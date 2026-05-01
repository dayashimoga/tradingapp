# ============================================================
# TradingBot — Multi-stage Production Docker Build
# ============================================================
FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ---- Dependencies stage ----
FROM base AS deps
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir ".[dashboard,alerts,ml,dev]"

# ---- Production stage ----
FROM base AS production
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy runtime config files
COPY config/ ./config/

# Create non-root user
RUN useradd --create-home --shell /bin/bash tradingbot
RUN mkdir -p /app/data && chown -R tradingbot:tradingbot /app
USER tradingbot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import tradingbot; print('ok')" || exit 1

EXPOSE 8000

# Default command
ENTRYPOINT ["tradingbot"]
CMD ["dashboard", "--host", "0.0.0.0", "--port", "8000"]
