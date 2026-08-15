# Contributing to z LLM Safety Gateway

Thanks for your interest in contributing! This project follows the standard
GitHub **Fork + Pull Request** workflow (DESIGN.md §19.2).

## Development Setup

```bash
# 1. Fork & clone, then:
cd z-llm-safety-gateway
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -e sdk
pip install -e .[grpc]
pip install ruff mypy pytest pytest-asyncio pytest-cov
```

## Code Style & Quality Gates

Before submitting, all of the following MUST pass:

```bash
ruff check src/ tests/ sdk/src/
mypy src/
pytest tests/ -q          # plus: PYTHONPATH=sdk/src (if SDK not installed)
```

- Line length: 100 (`ruff` enforced)
- Type hints required on all public functions
- Coverage: the project maintains >80% unit test coverage (currently ~93%)
- No new third-party runtime dependencies without discussion

## Commit Format

Use conventional commits with a version scope for release-feature changes:

```
feat(v0.x.y): short summary — detail list
fix: description
docs: description
chore: description
```

Example: `feat(v0.5.0): Plugin Ecosystem — in-process plugins, gRPC sidecar, Detector SDK`

## PR Workflow

1. Create a branch from `main` (e.g. `fix/rate-limit-retry-after`)
2. Make your change; add/update tests for any behavior change
3. Run the quality gates above locally
4. Open a PR using the [pull request template](.github/PULL_REQUEST_TEMPLATE.md)
5. A maintainer will review; address feedback and keep the branch up to date

## Areas We Value

- New detectors (in-process or gRPC) — see [Plugin Development](docs/plugin-development.md)
- Performance improvements with benchmark evidence ([benchmarks](tests/benchmarks/))
- Test coverage and accuracy sample sets (`tests/accuracy/`)
- Documentation fixes (all commands in docs are verified against the implementation)

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
