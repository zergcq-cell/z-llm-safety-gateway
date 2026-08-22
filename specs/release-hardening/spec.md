# Capability: release-hardening

## ADDED Requirements

- **REQ-REL-001**：gateway/SDK SHALL 以 0.1.1 构建四个有效产物，并在干净环境安装、运行三个入口。
- **REQ-REL-002**：生产依赖 SHALL 无未处置漏洞；豁免必须有 ID、理由、影响和到期日。
- **REQ-REL-003**：dry-run SHALL 验证产物和精确 CHANGELOG 内容，且 SHALL NOT 发布。
- **REQ-REL-004**：Gate 3 后 v0.1.1 tag SHALL 驱动全绿 CI 与包含四个产物的 GitHub Release。
