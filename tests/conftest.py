"""Shared pytest fixtures and configuration."""

import pytest


@pytest.fixture
def sample_config_yaml() -> str:
    """Minimal valid YAML config for testing."""
    return """
server:
  host: "127.0.0.1"
  port: 8080

providers:
  - name: "openai"
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
  - name: "local_llama"
    type: "openai_compatible"
    base_url: "http://localhost:11434/v1"
  - name: "azure"
    type: "azure_openai"
    base_url: "https://my-resource.openai.azure.com"
    api_key: "${AZURE_API_KEY}"
    api_version: "2024-06-01"

routing:
  rules:
    - pattern: "gpt-4*"
      provider: "openai"
    - pattern: "gpt-3.5*"
      provider: "openai"
    - pattern: "llama*"
      provider: "local_llama"
    - pattern: "azure-*"
      provider: "azure"

pipeline:
  mode: "sync"
  detectors: []

security:
  timeout:
    upstream: 120

audit:
  enabled: false
  sanitize_logs: true

observability:
  metrics_enabled: false
  tracing_enabled: false
"""
