# Project Principles

These four principles are the project's long-term constitution. They take precedence over
short-term convenience and specific implementation choices. Every proposal, STDD change,
architecture decision, and pull request MUST consider all four explicitly.

When principles appear to conflict, the trade-off MUST be documented rather than hidden. A
change that intentionally departs from a principle requires an explicit design decision and
maintainer approval.

## 1. Capabilities Are Plugins; Execution Is Flow; the Core Stays Small

All domain capabilities—including safety checks, classification, transformation, routing,
approval, and output handling—belong in plugins. Plugins declare capabilities and return
structured results; they do not control the end-to-end process.

Flow configuration determines how a request enters and exits the gateway, which capabilities
run, and how execution branches, joins, retries, degrades, or stops. A Flow can contain another
Flow as a node, and nested Flows obey the same input, output, lifecycle, and observability
contracts as other nodes.

The core provides only the durable runtime mechanisms: contracts, loading, lifecycle, isolation,
Flow execution, context propagation, result aggregation, and observability. Domain logic and
deployment-specific policy MUST NOT accumulate in the core.

> Capabilities belong to plugins. Order belongs to Flow. The core provides the runtime.

## 2. Policy Is Explicit; Failure Is Never Silent

Safety and availability trade-offs are policy choices, not hidden implementation decisions.
Timeouts, uncertain results, unavailable plugins, partial failures, bypasses, fallbacks, and
degraded execution MUST have explicit behavior in Flow or configuration.

Every skip or degradation has a reason and an observable signal. `fail_open`, `fail_closed`, and
their defaults are documented and auditable. Invalid or contradictory policy is rejected as
early as practical, preferably at startup.

> A policy may choose its trade-offs, but every choice and degradation is explicit, visible,
> and traceable.

## 3. Boundaries Are Transparent; Contracts Are Stable

Unless a Flow explicitly requires intervention, the gateway preserves the protocol and semantics
between clients and upstream providers. It does not rewrite data unexpectedly, bind users to a
specific provider, detector technology, programming language, or deployment model, or impose
unbounded latency and resource cost.

Plugin, Flow, provider, and public API contracts are versioned, testable, and governed by a
documented compatibility policy. New capabilities evolve through those contracts rather than
through knowledge of a particular implementation.

> Transparent at the boundaries, extensible inside, and built on stable contracts.

## 4. Every Safety Decision Has Evidence; Data Is Protected by Default

For every allow, block, flag, modification, fallback, and degradation, the gateway can explain
which Flow and node acted, which plugin and version ran, which policy applied, and what evidence
supported the outcome. Decisions are reproducible and auditable within the limits of configured
retention.

Auditability does not justify collecting everything. The gateway minimizes collection and
retention, avoids storing raw content by default, sanitizes logs, and requires explicit policy to
retain additional sensitive data.

> Decisions are explainable, reproducible, and auditable; data is minimized and protected by
> default.

## Required Principle Check

Every proposed or completed change MUST answer:

1. **Plugin / Flow:** Does domain behavior remain in plugins and composition remain in Flow? Does
   the core stay limited to runtime mechanisms?
2. **Explicit policy / failure:** Are decisions, defaults, failure modes, bypasses, and degradation
   explicit and observable?
3. **Transparency / contracts:** Does the change preserve boundary semantics and compatibility?
   Are latency and resource costs bounded?
4. **Evidence / data:** Can outcomes be explained and audited without collecting more sensitive
   data than necessary?

“Not applicable” is acceptable only with a short explanation. This check complements the STDD
workflow: principles govern direction; specs and tests prove the chosen behavior.
