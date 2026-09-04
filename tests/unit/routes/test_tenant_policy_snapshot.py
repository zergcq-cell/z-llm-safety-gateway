"""All-path request snapshot isolation for compiled tenant policy bundles."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from z_llm_safety_gateway.detectors.status import DetectorState, DetectorStatusRegistry
from z_llm_safety_gateway.routes.chat import _enforce_detector_availability
from z_llm_safety_gateway.tenancy.policy import TenantRuntimeBundle


class _Detector:
    name = "sentinel"
    version = "1.0.0"


def _bundle(policy_id: str) -> TenantRuntimeBundle:
    detector = _Detector()
    statuses = DetectorStatusRegistry()
    statuses.register(
        direction="input",
        name="sentinel",
        detector_type="builtin",
        required=False,
        on_error="fail_open",
        timeout_seconds=1.0,
    )
    statuses.transition("input", "sentinel", DetectorState.HEALTHY, detector=detector)
    policy_marker = object()
    return TenantRuntimeBundle(
        policy_id=policy_id,
        input_flow_identity=(f"{policy_id}-input", "1.0.0"),
        output_flow_identity=(f"{policy_id}-output", "1.0.0"),
        routing_profile_id=policy_id,
        input_detectors=(detector,),
        output_detectors=(),
        input_detector_configs={"sentinel": {"marker": policy_id}},
        output_detector_configs={},
        status_registry=statuses,
        input_detector_policies={"sentinel": policy_marker},  # type: ignore[arg-type]
        output_detector_policies={},
    )


def _request(bundle: TenantRuntimeBundle) -> Any:
    return SimpleNamespace(
        state=SimpleNamespace(
            request_id=f"request-{bundle.policy_id}",
            _tenant_runtime_bundle=bundle,
        ),
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    flow_runtime=SimpleNamespace(max_evidence_size=262144)
                ),
                input_detectors=(object(),),
                output_detectors=(object(),),
                input_detector_configs={"global": {"marker": "global"}},
                output_detector_configs={"global": {"marker": "global"}},
                input_flow_identity=("global-input", "1.0.0"),
                output_flow_identity=("global-output", "1.0.0"),
                input_detector_policies={"global": object()},
                output_detector_policies={"global": object()},
            )
        ),
    )


def test_request_snapshot_captures_one_bundle_for_every_stage() -> None:
    """TC-TPR-005/TC-DDF-010: all stages retain the originating bundle."""
    acme_bundle = _bundle("acme-policy")
    globex_bundle = _bundle("globex-policy")
    acme_request = _request(acme_bundle)
    globex_request = _request(globex_bundle)

    _enforce_detector_availability(acme_request)
    _enforce_detector_availability(globex_request)
    acme_snapshot = acme_request.state.flow_snapshot
    globex_snapshot = globex_request.state.flow_snapshot

    acme_request.state._tenant_runtime_bundle = globex_bundle
    stages = (
        "input",
        "sync-output",
        "async-output",
        "sliding-window",
        "buffer",
        "post-audit",
    )
    acme_views = tuple(
        acme_snapshot.stage(
            "input" if stage == "input" else "output",
            stage,
        )
        for stage in stages
    )

    assert len({view.snapshot_id for view in acme_views}) == 1
    assert acme_snapshot.input_flow_identity == ("acme-policy-input", "1.0.0")
    assert globex_snapshot.input_flow_identity == ("globex-policy-input", "1.0.0")
    assert acme_snapshot.input_detector_configs["sentinel"]["marker"] == "acme-policy"
    assert globex_snapshot.input_detector_configs["sentinel"]["marker"] == "globex-policy"
    assert set(acme_snapshot.input_detector_policies or {}) == {"sentinel"}
    assert set(globex_snapshot.input_detector_policies or {}) == {"sentinel"}
    assert "global" not in acme_snapshot.input_detector_configs
    assert "global" not in (acme_snapshot.input_detector_policies or {})


def test_request_snapshot_deep_freezes_nested_detector_config() -> None:
    """TC-TPR-005: one request cannot mutate a later request's nested config."""
    bundle = _bundle("acme-policy")
    nested = ["private-word"]
    bundle = replace(
        bundle,
        input_detector_configs={"sentinel": {"words": nested}},
    )
    first = _request(bundle)
    second = _request(bundle)
    _enforce_detector_availability(first)
    _enforce_detector_availability(second)

    with pytest.raises(TypeError):
        first.state.flow_snapshot.input_detector_configs["sentinel"]["words"][0] = "x"
    assert second.state.flow_snapshot.input_detector_configs["sentinel"]["words"] == (
        "private-word",
    )
