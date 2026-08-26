# Release tool lock maintenance

`release-tools.lock` is the reproducible tool environment used by both release build and audit
jobs. Direct inputs are reviewed in `release-tools.in`; all transitive versions and hashes are
generated, never edited by hand. Platform-conditional dependencies used by the Ubuntu release
runner are explicit inputs so regeneration on macOS cannot silently omit them.

Regenerate in a clean Python 3.12 virtual environment:

```console
python3.12 -m venv /tmp/zlg-release-lock
/tmp/zlg-release-lock/bin/python -m pip install pip-tools==7.6.1
/tmp/zlg-release-lock/bin/pip-compile --generate-hashes --resolver=backtracking \
  --allow-unsafe --strip-extras \
  --output-file requirements/release-tools.lock requirements/release-tools.in
```

Review every version and hash change before merging. Dependabot changes to GitHub Actions must
also be verified against the official Node 24 `action.yml`, then pinned to the reviewed full
commit SHA with the semantic version retained as an inline comment.
