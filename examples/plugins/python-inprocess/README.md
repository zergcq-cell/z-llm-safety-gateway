# Python In-process Detector Example

A complete example of an **in-process** plugin: the detector runs inside the
gateway process and is discovered via Python entry points.

## What it does

`AcmeKeywordDetector` enforces a simple corporate policy:
- blocks content containing configured keywords (`block_keywords`)
- redacts (masks) content containing configured keywords (`redact_keywords`)

## Files

| File | Purpose |
|------|---------|
| `src/acme_keyword_detector/detector.py` | The detector implementation (SDK `Detector` subclass) |
| `pyproject.toml` | Package metadata + `z_llm_safety_gateway.detectors` entry point |
| `tests/test_detector.py` | Unit tests using `z_llm_safety_gateway_sdk.testing` |

## Install & use

```bash
# 1. install the SDK (once)
pip install -e ../../../sdk

# 2. install this plugin (registers the entry point)
pip install -e .

# 3. configure the gateway
cat > config/plugin-example.yaml <<'YAML'
pipeline:
  detectors:
    input:
      - name: acme_keyword
        enabled: true
        config:
          block_keywords: ["competitor-x", "layoff"]
          redact_keywords: ["acme-secret"]
          block_threshold: 0.85
YAML
```

The gateway discovers `acme_keyword` automatically at startup. Verify with:

```bash
zlg detectors list          # should include acme_keyword
zlg detectors test acme_keyword --input "competitor-x is launching"
```

## Run the tests

```bash
PYTHONPATH=../../../sdk/src:src python3 -m pytest tests -q
```

## Key takeaway

An in-process plugin is just a `z_llm_safety_gateway_sdk.Detector` subclass
plus one entry point line in `pyproject.toml`. No server, no protobuf, no
serialization — the gateway calls your class methods directly in-process.
