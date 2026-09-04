# STDD Gate Confirmation Contract

Use this shared contract whenever a phase requires an explicit user gate.

1. Finish every mandatory phase step and generate the phase artifacts before asking for confirmation.
2. Present a truthful, compact summary of completed work, validation results, design adjustments, skipped checks, known failures, and unresolved risks.
3. State which gate is pending and the exact next phase that confirmation authorizes.
4. Wait for an explicit user confirmation. Silence, long-range mode, prior phase approval, or broad implementation authorization never approves a gate.
5. If the user requests changes, keep the gate pending, update the relevant artifacts, rerun affected validation, and ask again.
6. Record the approval and timestamp in the active change `.stdd.yaml` only after explicit confirmation.

Gate 3 additionally requires `test-report.md` and `design-adjustments.md` (or an explicit no-adjustment record). Git delivery is separate authority unless the user explicitly granted it.
