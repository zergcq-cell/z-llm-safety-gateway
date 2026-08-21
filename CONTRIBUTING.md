# Contributing to z LLM Safety Gateway

Thanks for your interest in contributing! This project follows the standard
GitHub **Fork + Pull Request** workflow (DESIGN.md §19.2).

Python 3.10–3.12 is supported. Python 3.12 is recommended for a new development
environment and is used for release builds.

## Development Setup

```bash
# 1. Fork & clone, then:
cd z-llm-safety-gateway
python3.12 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,grpc]"
pip install -e sdk
```

## Spec and Test Driven Changes

This repository uses STDD for code changes: Understand → Spec → Slice → Build → Verify →
Deliver. Discuss the requirement and acceptance criteria before implementation, add a failing
test first, then make the minimum implementation pass. Maintainers track active changes under
`changes/`; run `python bin/stdd --help` to inspect the project toolchain.

Documentation-only corrections still need link and consistency checks, but do not need to invent
behavioral tests.

## Code Style & Quality Gates

Before submitting, all of the following MUST pass:

```bash
ruff check src/ tests/ sdk/src/ tools/ examples/plugins/python-inprocess/src \
  examples/plugins/python-inprocess/tests examples/plugins/python-grpc/src \
  examples/plugins/python-grpc/tests
mypy src/ sdk/src tools/
PYTHONPATH=sdk/src pytest tests/ --cov=src/z_llm_safety_gateway --cov-fail-under=90 -q
```

- Line length: 100 (`ruff` enforced)
- Type hints required on all public functions
- Coverage: the release gate is at least 90% (currently about 93%)
- No new third-party runtime dependencies without discussion

## Commit Format

Use conventional commits with a version scope for release-feature changes:

```
feat(v0.x.y): short summary — detail list
fix: description
docs: description
chore: description
```

Example: `feat(v0.2.0): add a new detector capability`

## PR Workflow

1. Create a branch from `main` (e.g. `fix/rate-limit-retry-after`)
2. Make your change; add/update tests for any behavior change
3. Run the quality gates above locally
4. Open a PR using the [pull request template](.github/PULL_REQUEST_TEMPLATE.md)
5. A maintainer will review; address feedback and keep the branch up to date

## Areas We Value

- New detectors (in-process or gRPC) — see [Plugin Development](docs/plugin-development.md)
- Performance improvements with benchmark evidence
  ([benchmark runner](tests/benchmarks/bench_pipeline.py))
- Test coverage and accuracy sample sets (`tests/accuracy/`)
- Documentation fixes (all commands in docs are verified against the implementation)

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).

All participation is also governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Report security
issues through the private process in the [Security Policy](SECURITY.md), not through a public PR.
