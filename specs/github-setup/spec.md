# Capability: github-setup

## MODIFIED Requirements

- **REQ-GH-004**：CI SHALL 覆盖 Python 3.10/3.11/3.12，发布构建使用 3.12。
- **REQ-GH-005**：Ruff SHALL 覆盖示例 tests，Mypy SHALL 覆盖 SDK，coverage SHALL ≥90%。
- **REQ-GH-006**：Dependabot SHALL 覆盖三类依赖，远程 quality/build/audit checks SHALL 全绿。


<!-- 合并自 2026-08-25-v0.2.2-release-reproducibility -->
# Capability: github-setup

## MODIFIED Requirements

### REQ-GH-007：GitHub workflows 使用官方 Node 24 Action 的已核验完整 SHA

- **SC-GH-008 · high**：checkout、setup-python、upload-artifact、download-artifact SHALL 分别固定到 design.md 核验的 40 位 commit SHA，并保留语义版本注释。
- **SC-GH-009 · high**：Dependabot SHALL 继续覆盖 root pip、SDK pip 和 GitHub Actions；Action 或 release lock 更新不得绕过 allowlist、hash 重新生成与 diff 审查。

### REQ-GH-008：事件、质量矩阵和权限保持最小且可验证

- **SC-GH-010 · high**：quality matrix SHALL 精确包含 Python 3.10/3.11/3.12；release 复用同一 CI 并依赖 quality/build/audit；非 release jobs 不得获得写权限，manual dispatch 不得具备 publish 路径。
- **SC-GH-011 · medium**：同一提交的 main CI、dry-run 和 tag Release SHALL 全绿且不得产生 Node.js 20 deprecation annotation；download-artifact digest mismatch 保持默认 error。

## Verification

- Canonical spec: `canonical/specs/code/github-setup.yaml`
- Agent checkpoints: `canonical/specs/agent/github-setup.yaml`
- Test cases: 4
- Official Action refs and node24 declarations are recorded in `design.md`
