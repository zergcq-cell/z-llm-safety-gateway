"""Observability package: Prometheus metrics and OpenTelemetry tracing.

Sub-modules:
- :mod:`z_llm_safety_gateway.observability.metrics` — Prometheus metrics
  collection, aligned with DESIGN.md section 12.5.
- :mod:`z_llm_safety_gateway.observability.tracing` — optional OpenTelemetry
  distributed tracing, aligned with DESIGN.md section 12.6.

Importing this package has no side effects: metrics are only initialized when
``observability.metrics.enabled`` is true, and tracing is only initialized when
``observability.tracing.enabled`` is true.
"""

from __future__ import annotations

from z_llm_safety_gateway.observability import metrics, tracing

__all__ = ["metrics", "tracing"]
