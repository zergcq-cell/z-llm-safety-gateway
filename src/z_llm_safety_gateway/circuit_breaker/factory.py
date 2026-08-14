"""Factory for building :class:`CircuitBreaker` instances from config.

v0.4.0 adds a ``CircuitBreakerConfig -> CircuitBreaker`` builder so that the
per-detector ``circuit_breaker`` config is actually wired into the pipeline
engine (previously the config was parsed but never injected, so the breaker
never took effect — see backlog B-04).
"""

from __future__ import annotations

from z_llm_safety_gateway.circuit_breaker.breaker import CircuitBreaker
from z_llm_safety_gateway.config.models import CircuitBreakerConfig, _parse_duration


def build_circuit_breaker(config: CircuitBreakerConfig) -> CircuitBreaker:
    """Build a :class:`CircuitBreaker` from its configuration.

    Args:
        config: The detector-level circuit breaker configuration.

    Returns:
        A configured :class:`CircuitBreaker` instance.
    """
    recovery_seconds = _parse_duration(config.recovery_timeout)
    return CircuitBreaker(
        failure_threshold=config.failure_threshold,
        recovery_timeout=recovery_seconds,
        fallback_action=config.fallback_action,
    )
