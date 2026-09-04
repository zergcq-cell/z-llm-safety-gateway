"""Trusted request policy resolution over precompiled runtime bundles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from z_llm_safety_gateway.config.models import TenancyConfig
from z_llm_safety_gateway.tenancy.context import TenantContext

if TYPE_CHECKING:
    from z_llm_safety_gateway.detectors.status import DetectorStatusRegistry
    from z_llm_safety_gateway.flow.detector_adapter import DetectorCapabilityCoordinator
    from z_llm_safety_gateway.flow.policy import ResolvedNodePolicy
    from z_llm_safety_gateway.pipeline.engine import PipelineEngine
    from z_llm_safety_gateway.providers.router import TenantRouterView

FlowIdentity = tuple[str, str]


@dataclass(frozen=True, slots=True)
class TenantPolicyContext:
    """Secret-free policy identity snapshot safe for evidence propagation."""

    tenant_id: str
    policy_id: str
    input_flow_identity: FlowIdentity | None
    output_flow_identity: FlowIdentity | None
    routing_profile_id: str
    contract_version: Literal["1.0"] = "1.0"


@dataclass(frozen=True, slots=True, repr=False)
class TenantRuntimeBundle:
    """Private app-scoped runtime handle for one compiled tenant policy."""

    policy_id: str
    input_flow_identity: FlowIdentity | None
    output_flow_identity: FlowIdentity | None
    routing_profile_id: str
    engine: PipelineEngine | None = None
    input_detectors: tuple[Any, ...] = ()
    output_detectors: tuple[Any, ...] = ()
    input_detector_configs: Mapping[str, Mapping[str, Any]] | None = None
    output_detector_configs: Mapping[str, Mapping[str, Any]] | None = None
    status_registry: DetectorStatusRegistry | None = None
    detector_coordinator: DetectorCapabilityCoordinator | None = None
    resolved_node_policies: Mapping[
        tuple[str, str, str], ResolvedNodePolicy
    ] | None = None
    input_detector_policies: Mapping[str, ResolvedNodePolicy] | None = None
    output_detector_policies: Mapping[str, ResolvedNodePolicy] | None = None
    router_view: TenantRouterView | None = None


@dataclass(frozen=True, slots=True, repr=False)
class TenantPolicyResolution:
    """One request's public policy context and private runtime bundle."""

    context: TenantPolicyContext
    bundle: TenantRuntimeBundle


class TenantPolicyUnavailableError(RuntimeError):
    """Raised when enabled tenancy has inconsistent runtime policy state."""


class TenantPolicyResolver:
    """Resolve trusted tenant identities through bounded O(1) mappings."""

    def __init__(
        self,
        tenancy: TenancyConfig,
        bundles: tuple[TenantRuntimeBundle, ...] | list[TenantRuntimeBundle],
    ) -> None:
        self.enabled = tenancy.enabled
        self._tenant_policy_ids: dict[str, str] = {
            tenant.id: tenant.policy_id
            for tenant in tenancy.tenants
            if tenant.policy_id is not None
        }
        self._bundles: dict[str, TenantRuntimeBundle] = {
            bundle.policy_id: bundle for bundle in bundles
        }
        self._require_executable = False

    def install_bundles(
        self,
        bundles: tuple[TenantRuntimeBundle, ...] | list[TenantRuntimeBundle],
    ) -> None:
        """Install fully compiled bundles during startup before serving requests."""
        installed = {bundle.policy_id: bundle for bundle in bundles}
        if any(not _is_executable_bundle(bundle) for bundle in installed.values()):
            raise TenantPolicyUnavailableError("tenant_policy_unavailable")
        self._bundles = installed
        self._require_executable = True

    def resolve(self, tenant: TenantContext | None) -> TenantPolicyResolution | None:
        """Resolve one trusted Context without consulting request-controlled data."""
        if not self.enabled:
            return None
        if tenant is None:
            raise TenantPolicyUnavailableError
        policy_id = self._tenant_policy_ids.get(tenant.tenant_id)
        if policy_id is None:
            raise TenantPolicyUnavailableError
        bundle = self._bundles.get(policy_id)
        if (
            bundle is None
            or bundle.policy_id != policy_id
            or (self._require_executable and not _is_executable_bundle(bundle))
        ):
            raise TenantPolicyUnavailableError
        context = TenantPolicyContext(
            tenant_id=tenant.tenant_id,
            policy_id=policy_id,
            input_flow_identity=bundle.input_flow_identity,
            output_flow_identity=bundle.output_flow_identity,
            routing_profile_id=bundle.routing_profile_id,
        )
        return TenantPolicyResolution(context=context, bundle=bundle)


def _is_executable_bundle(bundle: TenantRuntimeBundle) -> bool:
    """Return whether every security-relevant runtime dependency was compiled."""
    return all(
        value is not None
        for value in (
            bundle.engine,
            bundle.input_detector_configs,
            bundle.output_detector_configs,
            bundle.status_registry,
            bundle.detector_coordinator,
            bundle.resolved_node_policies,
            bundle.input_detector_policies,
            bundle.output_detector_policies,
            bundle.router_view,
        )
    )
