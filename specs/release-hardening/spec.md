# Capability: release-hardening

## ADDED Requirements

- **REQ-REL-001**：gateway/SDK SHALL 以 0.1.1 构建四个有效产物，并在干净环境安装、运行三个入口。
- **REQ-REL-002**：生产依赖 SHALL 无未处置漏洞；豁免必须有 ID、理由、影响和到期日。
- **REQ-REL-003**：dry-run SHALL 验证产物和精确 CHANGELOG 内容，且 SHALL NOT 发布。
- **REQ-REL-004**：Gate 3 后 v0.1.1 tag SHALL 驱动全绿 CI 与包含四个产物的 GitHub Release。


<!-- 合并自 2026-08-23-v0.2.1-release-version-hotfix -->
# Capability: release-hardening

## MODIFIED Requirements

### REQ-REL-005：Gateway tag 与独立 SDK 版本按角色严格校验

- **SC-REL-008 · high**：给定 Gateway `0.2.1`、SDK `0.1.1` 和非空 0.2.1 CHANGELOG，使用 `v0.2.1` 校验时 SHALL 接受该独立版本组合。
- **SC-REL-009 · high**：Gateway package 或 runtime 与 tag 不一致时 SHALL 非零失败，并明确标识 gateway mismatch。
- **SC-REL-010 · high**：SDK package/runtime 不一致时 SHALL 非零失败，不得静默选择任一值。
- **SC-REL-011 · high**：0.2.1 CHANGELOG 缺失或为空时 SHALL 非零失败；有效 notes 不得包含相邻版本正文。

### REQ-REL-006：v0.2.1 Release 构建并验证两个独立版本的四个产物

- **SC-REL-012 · high**：构建 SHALL 恰好生成 Gateway `0.2.1` 与 SDK `0.1.1` 的两个 wheel、两个 sdist，四个 metadata 检查通过。
- **SC-REL-013 · high**：两个 wheel 在干净环境安装后，三个 CLI SHALL 成功；SDK wheel 另可无 Gateway 独立安装。

### REQ-REL-007：v0.2.1 由不可变新 tag 和完整远程质量链发布

- **SC-REL-014 · high**：manual dry-run SHALL 不发布且无静态版本默认；tag release SHALL 依赖 quality/build/audit。
- **SC-REL-015 · medium**：只有 main 同一提交的 Python 3.10/3.11/3.12 CI 全绿后才允许创建 `v0.2.1`。
- **SC-REL-016 · medium**：新 tag 的 Release workflow SHALL 全绿，Release SHALL 包含精确 notes 和四个验证产物。
- **SC-REL-017 · medium**：`v0.2.0` tag object 与 peeled commit SHALL 始终保持基线值，不得删除、移动或覆盖。

## Verification

- Canonical spec: `canonical/specs/code/release-hardening.yaml`
- Agent checkpoints: `canonical/specs/agent/release-hardening.yaml`
- Test cases: 10
- L3 anchors: `2026-08-20-v0.1.1-release-hardening`, `2026-08-22-v0.2.0-flow-foundation`
