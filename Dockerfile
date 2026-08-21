# --- Stage 1: Builder ---
FROM python:3.10-slim AS builder

WORKDIR /build

# Install build dependencies (gcc for C extensions like pyahocorasick)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies into a target directory
RUN pip install --no-cache-dir --target=/install ".[grpc]"

# --- Stage 2: Runtime ---
FROM python:3.10-slim

WORKDIR /app

# Copy installed packages from builder (includes compiled C extensions)
COPY --from=builder /install /usr/local/lib/python3.10/site-packages

# Copy application source
COPY --from=builder /build/src/z_llm_safety_gateway /app/z_llm_safety_gateway

# Copy default config
COPY config/gateway.yaml /app/config/gateway.yaml

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the gateway
ENTRYPOINT ["python", "-m", "z_llm_safety_gateway"]
CMD ["--config", "/app/config/gateway.yaml"]
