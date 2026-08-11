"""Abstract base class and error type for LLM provider adapters."""

from __future__ import annotations

import abc
from typing import Any

import httpx

from z_llm_safety_gateway.config.models import ProviderConfig


class ProviderError(Exception):
    """Provider forwarding error with provider name and original error details.

    Attributes:
        provider_name: Name of the provider that produced the error.
        message: Human-readable error message.
        status_code: Original HTTP status code from the provider (if applicable).
        retry_after: Value of the Retry-After header from the provider (if present).
    """

    def __init__(
        self,
        provider_name: str,
        message: str,
        status_code: int | None = None,
        retry_after: str | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(message)


class BaseProvider(abc.ABC):
    """Abstract base class for LLM provider adapters.

    Subclasses implement provider-specific header, URL, and query parameter
    construction by overriding ``_build_headers``, ``_build_url``, and
    ``_build_params``.  The shared :meth:`_send` method handles timeout,
    network-error, and HTTP-error wrapping uniformly.
    """

    def __init__(self, config: ProviderConfig, timeout: float = 120.0) -> None:
        self.config = config
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # Customisation hooks (overridden by subclasses)
    # ------------------------------------------------------------------ #

    def _build_url(self) -> str:
        """Return the full URL for the chat-completions endpoint."""
        return f"{self.config.base_url}/chat/completions"

    def _build_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Return merged request headers.  Subclasses override to add auth."""
        return {**headers, "Content-Type": "application/json"}

    def _build_params(self) -> dict[str, str] | None:
        """Return query parameters.  Subclasses override to add params."""
        return None

    # ------------------------------------------------------------------ #
    # Shared request-sending logic
    # ------------------------------------------------------------------ #

    async def _send(
        self, request: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        """Forward *request* to the provider and wrap errors as ``ProviderError``."""
        url = self._build_url()
        merged_headers = self._build_headers(headers)
        params = self._build_params()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, json=request, headers=merged_headers, params=params
                )
        except httpx.TimeoutException:
            raise ProviderError(
                provider_name=self.config.name,
                message=f"Provider '{self.config.name}' timeout after {self.timeout}s",
            ) from None
        except httpx.HTTPError:
            raise ProviderError(
                provider_name=self.config.name,
                message=f"Network error connecting to provider '{self.config.name}'",
            ) from None

        if response.status_code >= 400:
            retry_after = response.headers.get("Retry-After")
            raise ProviderError(
                provider_name=self.config.name,
                message=f"Provider '{self.config.name}' returned HTTP {response.status_code}",
                status_code=response.status_code,
                retry_after=retry_after,
            )

        return response

    # ------------------------------------------------------------------ #
    # Public API (implemented by each subclass)
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def forward_request(
        self, request: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        """Forward a request to the provider's API endpoint."""
        ...
