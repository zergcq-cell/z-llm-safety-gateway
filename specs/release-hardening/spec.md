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


<!-- 合并自 2026-08-25-v0.2.2-release-reproducibility -->
# Capability: release-hardening

## MODIFIED Requirements

### REQ-REL-008：v0.2.2 发布工具链由仓库内带哈希锁文件确定

- **SC-REL-018 · high**：release lock SHALL 精确锁定 pip 26.2.1、build 1.5.0、twine 7.0.0、pip-audit 2.10.1、hatchling 1.32.0 及全部传递依赖 hashes；build/audit 使用同一 lock，不再浮动安装；lock regeneration 固定使用 pip-tools 7.6.1。
- **SC-REL-019 · high**：Gateway 与 SDK SHALL 使用锁定 Hatchling 和 `build --no-isolation`，生成 Gateway 0.2.2 / SDK 0.1.1 的两个 wheel、两个 sdist，并通过 Twine、metadata 与 clean runner 三 CLI 检查。

### REQ-REL-009：tag Release 在私有 draft 精确验证后才公开

- **SC-REL-020 · high**：workflow_dispatch SHALL 只验证；tag release SHALL 依赖 quality/build/audit，只有 release job 获得 `contents: write`，draft create 位于 publish 之前。
- **SC-REL-021 · high**：draft 创建前 SHALL 从本地 `dist/` 四产物生成按文件名绑定的 SHA-256 清单；draft/public 校验 SHALL 精确检查 tag、CHANGELOG body、四资产 multiset、uploaded 状态、远程 digest 与同名本地产物 SHA-256、draft/prerelease 状态与 peeled commit；不得只检查 digest 格式，不得以 targetCommitish 替代 peeled tag。
- **SC-REL-022 · high**：已有 Release、非 404、payload/digest/ref 错配或 publish 后异常 SHALL 硬失败；失败 draft 保留，任何 tag 不自动删除或移动，错误不得泄漏敏感上下文。

### REQ-REL-010：发布证据与远程状态可机器审计且数据有界

- **SC-REL-023 · high**：发布后 SHALL 生成稳定 schema、确定性排序、公开字段白名单的 evidence，并以 `retention-days: 90` 上传为 Actions artifact，不成为第五个 Release asset。
- **SC-REL-024 · medium**：Release absence SHALL 只接受明确 HTTP 404；401/403/429/5xx、网络或无效 JSON 全部失败。
- **SC-REL-025 · medium**：Gate 3 后同 SHA main CI 与 dry-run 成功后，SHALL 在 tag 创建前执行独立 checkpoint，证明 v0.2.2 Release 明确 404 且远程 tag 不存在；随后 v0.2.2 tag workflow、annotations、evidence 和历史 refs 验收 SHALL 全部成功，v0.2.0/v0.2.1 保持不变。

## Verification

- Canonical spec: `canonical/specs/code/release-hardening.yaml`
- Agent checkpoints: `canonical/specs/agent/release-hardening.yaml`
- Test cases: 8
- L3 anchors: `2026-08-20-v0.1.1-release-hardening`, `2026-08-23-v0.2.1-release-version-hotfix`
