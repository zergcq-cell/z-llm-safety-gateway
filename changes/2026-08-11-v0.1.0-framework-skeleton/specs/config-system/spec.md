# config-system - Behavioral Specification (Human View)

> **Change**: 2026-08-11-v0.1.0-framework-skeleton
> **Capability**: config-system
> **Created**: 2026-08-11T00:00:00+08:00
> **Confidence**: high

## Description

YAML configuration loading with Pydantic v2 schema validation, environment variable interpolation (`${VAR_NAME}`), and startup-time configuration validation. Invalid configuration produces clear error messages and prevents the gateway from starting.

---

## Requirements

### REQ-001: Load YAML Config File Using yaml.safe_load

**Description**: The config loader reads YAML files using `yaml.safe_load`.

**Confidence**: high

#### SC-001: Parse valid YAML into dictionary

- **Given**: a valid YAML config file containing server, providers, routing, pipeline, detectors, security, audit, observability, and model_cache sections
- **When**: the config loader reads the file
- **Then**: the loader **SHALL** parse the YAML content using `yaml.safe_load` and return a parsed dictionary
- **And**:
  - the loader **SHALL NOT** use `yaml.load` (unsafe) for parsing
  - the parsed dictionary **SHALL** preserve the YAML structure including nested objects and lists

#### SC-002: YAML syntax errors caught before Pydantic validation

- **Given**: a YAML config file with valid syntax but structurally incomplete (e.g., missing providers section)
- **When**: the config loader reads the file
- **Then**: the loader **SHALL** parse the YAML successfully and defer structural validation to the Pydantic schema layer
- **And**:
  - YAML syntax errors **SHALL** produce a parse error before Pydantic validation

---

### REQ-002: Interpolate ${VAR_NAME} Patterns with os.environ Values

**Description**: Environment variable interpolation replaces `${VAR_NAME}` patterns with `os.environ` values before Pydantic validation.

**Confidence**: high

#### SC-003: Replace ${VAR_NAME} with environment variable value

- **Given**: a YAML config file containing `api_key: ${OPENAI_API_KEY}` and an environment variable `OPENAI_API_KEY` set to `sk-test123`
- **When**: the config loader reads and processes the file
- **Then**: the loader **SHALL** replace `${OPENAI_API_KEY}` with the value `sk-test123` before passing to Pydantic validation
- **And**:
  - the interpolation **SHALL** occur recursively across all nested YAML values (strings in lists, dicts, etc.)
  - the interpolation **SHALL** occur before Pydantic model validation so the validator sees the resolved value
  - the pattern **SHALL** match the exact format `${VAR_NAME}` (dollar sign, curly braces, variable name, closing brace)

#### SC-004: Unset env var resolves to empty string

- **Given**: a YAML config file containing `api_key: ${UNSET_VAR}` and no environment variable `UNSET_VAR` is set
- **When**: the config loader reads and processes the file
- **Then**: the loader **SHALL** resolve `${UNSET_VAR}` to an empty string (`''`) rather than crashing
- **And**:
  - the resolved empty string **SHALL** be passed to Pydantic validation
  - if the field is required (e.g., `api_key` for openai provider), Pydantic validation **SHALL** then produce a validation error

---

### REQ-003: Pydantic v2 Models Validate All Config Sections

**Description**: Pydantic v2 models validate all config sections (server, providers, routing, pipeline, detectors, security, audit, observability, model_cache).

**Confidence**: high

#### SC-005: Valid config produces typed GatewayConfig instance

- **Given**: a fully valid config dictionary (after env var interpolation) with all sections present and correctly typed
- **When**: the config is validated through the `GatewayConfig` Pydantic v2 model
- **Then**: the model **SHALL** validate successfully and return a typed `GatewayConfig` instance
- **And**:
  - each config section (server, providers, routing, pipeline, detectors, security, audit, observability, model_cache) **SHALL** have a corresponding Pydantic model
  - the `GatewayConfig` **SHALL** be the root model containing all sub-sections
  - type annotations **SHALL** enforce correct types (e.g., `server.port` as int, `server.host` as str)

#### SC-006: Type mismatch produces ValidationError

- **Given**: a config dictionary where `server.port` is a string `'not_a_number'` instead of an integer
- **When**: the config is validated through the `GatewayConfig` Pydantic v2 model
- **Then**: Pydantic **SHALL** raise a `ValidationError` indicating the type mismatch for `server.port`
- **And**:
  - the validation error **SHALL** include the field path and the expected type
  - the validation error **SHALL** prevent the config from being loaded

---

### REQ-004: Cross-field Validation: block_threshold > flag_threshold

**Description**: Cross-field validation ensures `block_threshold` is strictly greater than `flag_threshold` for detectors.

**Confidence**: high

#### SC-007: Reversed thresholds rejected

- **Given**: a config dictionary with a detector having `block_threshold: 0.50` and `flag_threshold: 0.85`
- **When**: the config is validated through the Pydantic v2 model with cross-field validation
- **Then**: the validator **SHALL** raise a validation error because `block_threshold` (0.50) is not greater than `flag_threshold` (0.85)
- **And**:
  - the error message **SHALL** state that `block_threshold` must be greater than `flag_threshold`
  - the error message **SHALL** include the detector name and both threshold values
  - the validation **SHALL** use `@model_validator(mode='after')` for the cross-field check

#### SC-008: Valid thresholds accepted

- **Given**: a config dictionary with a detector having `block_threshold: 0.85` and `flag_threshold: 0.50`
- **When**: the config is validated through the Pydantic v2 model
- **Then**: the validator **SHALL** accept the configuration because `block_threshold` (0.85) is greater than `flag_threshold` (0.50)
- **And**:
  - no validation error **SHALL** be raised for valid threshold values

#### SC-009: Equal thresholds rejected

- **Given**: a config dictionary with a detector having `block_threshold: 0.85` and `flag_threshold: 0.85` (equal)
- **When**: the config is validated through the Pydantic v2 model
- **Then**: the validator **SHALL** raise a validation error because `block_threshold` must be strictly greater than `flag_threshold`
- **And**:
  - equal values **SHALL** be rejected, not just reversed values

---

### REQ-005: Routing Conflict Detection (Overlapping Glob Patterns)

**Description**: Overlapping glob patterns in routing rules produce a warning at startup.

**Confidence**: high

#### SC-010: Overlapping patterns produce warning

- **Given**: a config dictionary with routing rules `'gpt-4*': openai` and `'gpt-*': openai` that overlap for model `gpt-4`
- **When**: the config validation runs routing conflict detection at startup
- **Then**: the validator **SHALL** emit a warning indicating that routing rules `gpt-4*` and `gpt-*` overlap
- **And**:
  - the warning **SHALL NOT** prevent startup (it is a warning, not an error)
  - the warning message **SHALL** identify which model(s) are affected by the overlap
  - the warning message **SHALL** state which rule wins (first match in YAML order)
  - the first matching rule in YAML order **SHALL** be used for routing at runtime

#### SC-011: Non-overlapping patterns produce no warning

- **Given**: a config dictionary with routing rules `'gpt-4*': openai` and `'llama*': local_llama` that do not overlap
- **When**: the config validation runs routing conflict detection
- **Then**: the validator **SHALL NOT** emit any overlap warning
- **And**:
  - no models **SHALL** match more than one routing rule

---

### REQ-006: Invalid Config Produces Clear Error and Prevents Startup

**Description**: Invalid configuration produces a clear, human-readable error message and prevents the gateway from starting.

**Confidence**: high

#### SC-012: Pydantic validation failure raises ConfigValidationError

- **Given**: a YAML config file with invalid content that fails Pydantic validation
- **When**: the config loader attempts to load and validate the config
- **Then**: the loader **SHALL** raise a `ConfigValidationError` with a clear, human-readable error message
- **And**:
  - the error message **SHALL** identify which field(s) failed validation
  - the error message **SHALL** include the expected vs. actual value where applicable
  - the `ConfigValidationError` **SHALL** prevent the gateway from starting
  - the error **SHALL** be raised at startup, not deferred to request time

#### SC-013: YAML syntax error produces parse error with location

- **Given**: a YAML config file with a syntax error (e.g., unbalanced brackets)
- **When**: the config loader attempts to parse the file
- **Then**: the loader **SHALL** raise an error with a message indicating the YAML syntax error and approximate location
- **And**:
  - the error **SHALL** prevent the gateway from starting
  - the error **SHALL NOT** be swallowed or silently ignored

---

### REQ-007: Missing Required Provider Fields Produce Error

**Description**: Missing required provider fields (e.g., `api_key` for openai) produce a validation error.

**Confidence**: high

#### SC-014: Missing api_key for openai provider rejected

- **Given**: a config dictionary with an openai provider that has no `api_key` field (or `api_key` resolves to empty string via unset env var)
- **When**: the config is validated through the Pydantic v2 model
- **Then**: the validator **SHALL** raise a validation error indicating that provider 'openai' is missing required field 'api_key'
- **And**:
  - the error message **SHALL** include the provider name and the missing field name
  - the error **SHALL** prevent the gateway from starting
  - the validation **SHALL** apply to provider type-specific required fields (e.g., `api_key` for openai and azure_openai)

#### SC-015: openai_compatible provider without api_key accepted

- **Given**: a config dictionary with an `openai_compatible` provider that has `base_url` but no `api_key`
- **When**: the config is validated through the Pydantic v2 model
- **Then**: the validator **SHALL** accept the configuration because `openai_compatible` providers do not require `api_key`
- **And**:
  - only providers of type `openai` and `azure_openai` **SHALL** require `api_key`
  - the `azure_openai` provider **SHALL** also require `api_version`

---

### REQ-008: Unset Env Var ${VAR} Resolves to Empty String

**Description**: Unset environment variables referenced via `${VAR}` resolve to an empty string rather than crashing.

**Confidence**: high

#### SC-016: Unset variable resolves to empty string without exception

- **Given**: a YAML config file containing a value `${TOTALLY_UNSET_VAR}` and the environment variable `TOTALLY_UNSET_VAR` is not set
- **When**: the config loader performs environment variable interpolation
- **Then**: the loader **SHALL** resolve `${TOTALLY_UNSET_VAR}` to an empty string (`''`)
- **And**:
  - the loader **SHALL NOT** raise a `KeyError` or any exception for unset variables
  - the interpolation **SHALL** use `os.environ.get('VAR_NAME', '')` semantics
  - if the resulting empty string fails subsequent Pydantic validation (e.g., required field), the error **SHALL** come from Pydantic, not from the interpolation step

#### SC-017: Mixed set and unset variables resolved in single recursive pass

- **Given**: a YAML config file containing multiple `${VAR}` references where some are set and some are unset
- **When**: the config loader performs environment variable interpolation
- **Then**: the loader **SHALL** resolve all set variables to their values and all unset variables to empty strings in a single pass
- **And**:
  - the interpolation **SHALL** be recursive, processing nested structures (lists, dicts) completely
  - partially resolved values (e.g., `prefix-${VAR}-suffix`) **SHALL** have `${VAR}` replaced inline

---

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-001 | YAML loaded via yaml.safe_load returns dict |
| CP-2 | SC-002 | YAML syntax error caught before Pydantic |
| CP-3 | SC-003 | ${VAR_NAME} interpolation replaces env var values |
| CP-4 | SC-004 | Unset env var resolves to empty string |
| CP-5 | SC-005 | Valid config produces typed GatewayConfig |
| CP-6 | SC-006 | Type mismatch produces ValidationError |
| CP-7 | SC-007 | Reversed thresholds (block < flag) rejected |
| CP-8 | SC-008 | Valid thresholds (block > flag) accepted |
| CP-9 | SC-009 | Equal thresholds rejected |
| CP-10 | SC-010 | Overlapping routing rules produce warning |
| CP-11 | SC-011 | Non-overlapping routing rules produce no warning |
| CP-12 | SC-012 | Invalid config raises ConfigValidationError |
| CP-13 | SC-013 | YAML syntax error prevents startup with location |
| CP-14 | SC-014 | Missing api_key for openai provider rejected |
| CP-15 | SC-015 | openai_compatible without api_key accepted |
| CP-16 | SC-016 | Unset env var resolves to empty string |
| CP-17 | SC-017 | Mixed env vars resolved in single recursive pass |
| CP-18 | -- | Full test suite pass |
| CP-19 | -- | Lint and type checks pass |
