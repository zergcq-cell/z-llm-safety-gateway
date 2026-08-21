# v0.1.1 发布后加固任务清单

## 1. STDD Toolchain Recovery（P0）

- [x] 1.1 建立失败测试：provenance、哈希、CLI help/status
- [x] 1.2 从官方固定 commit vendoring `bin/stdd` 与 `stdd/`，补 MIT notice
- [x] 1.3 建立失败测试：archived canonical 与 structure backfill
- [x] 1.4 实现临时兼容工作区、canonical 校验和幂等结构 merge
- [x] 1.5 初始化经验库并补录三个真实模式
- [x] 1.6 通过 TC-STDD-001～006

## 2. GitHub Quality + Detector SDK（P0）

- [x] 2.1 保留 Ruff/Mypy 失败基线（示例 imports、SDK Any return）
- [x] 2.2 扩大 CI Ruff/Mypy scope 和 Python 3.10/3.11/3.12 matrix
- [x] 2.3 修复项目拥有代码的 Ruff/Mypy 错误
- [x] 2.4 同步 SDK 0.1.1 版本并扩充契约测试
- [x] 2.5 通过 TC-GH-001～002、TC-SDK-001～002

## 3. Release Hardening（P0）

- [x] 3.1 建立版本、workflow、构建产物、CHANGELOG 的失败契约测试
- [x] 3.2 更新 gateway/SDK 0.1.1 与 CHANGELOG/Release notes
- [x] 3.3 构建两个 wheel + 两个 sdist，执行 metadata check
- [x] 3.4 在临时干净环境安装并验证三个 CLI 入口
- [x] 3.5 增加并运行 pip-audit，记录零漏洞或显式豁免
- [x] 3.6 完成 Dependabot 与 Release workflow dry-run 契约
- [x] 3.7 通过 TC-REL-001～006、TC-GH-003、TC-SDK-003

## 4. Compose + Benchmark（P0/P1）

- [x] 4.1 建立 Compose 不变量与 benchmark 部分 suite 测试
- [x] 4.2 两个 Compose 通过 `docker compose config`
- [x] 4.3 Docker daemon 可用时完成有界健康冒烟与清理
- [x] 4.4 运行 latency/throughput/all 并生成可比较报告
- [x] 4.5 通过 TC-DEPL-001～003、TC-BENCH-001～002

## 5. Governance + Project Docs（P0/P1/P2）

- [x] 5.1 建立治理内容、版本口径、Quick Start 和链接失败测试
- [x] 5.2 新增 SECURITY.md 与 CODE_OF_CONDUCT.md
- [x] 5.3 校对 CONTRIBUTING、Issue/PR 模板与 README 入口
- [x] 5.4 统一 Python/版本/配置文档并实测 Quick Start
- [ ] 5.5 验证或创建 GitHub labels 与 v0.1.1/v0.2.0 milestones（已只读验证；Gate 3 后写远程）
- [ ] 5.6 通过 TC-GOV-001～003、TC-DOCS-001～003（本地 6/6；TC-GOV-003 远程部分待 Gate 3）

## 6. Verify + Deliver Checkpoint（P0）

- [x] 6.1 全量 pytest/cov、Ruff、Mypy、构建、audit、Compose、benchmark
- [ ] 6.2 执行多版本/远程可验证项并记录环境证据（本地 3.10 完成；3.11/3.12 与远程 CI 待 Gate 3）
- [x] 6.3 完成 diff review、L3 锚定和 12 类失败模式检查
- [x] 6.4 生成 test-report 与 design-adjustments，进入 Gate 3
- [ ] 6.5 Gate 3 后提交、push、创建 v0.1.1 tag 并验证 CI/Release
