# v0.1.1 发布后加固 Phase 5 测试报告

> Change：`2026-08-20-v0.1.1-release-hardening`
> 模式：thorough / full_auto / L3
> 测试日期：2026-08-21
> 本地环境：macOS，Python 3.10.20，Docker 29.x
> Gate 3：用户于 2026-08-21 11:04 +08:00 明确确认，已进入 Phase 6 Deliver
> 远程写入状态：报告生成时尚未 push/tag/release 或修改 GitHub 治理

## 1. 总体结论

本地 Phase 5 质量门全部通过，可进入 Gate 3。31 个计划 TC 中，28 个本地/运行态 TC 已完成；3 个必须依赖 Gate 3 后远程状态的 TC 保持 PENDING，不伪造 PASS。

| 指标 | 结果 |
|------|------|
| 最终自动化回归 | 904 passed / 1 skipped / 0 failed |
| 源码覆盖率 | 92.85%（门槛 90%） |
| Ruff | passed |
| Mypy strict | 88 source files，0 issues |
| 计划 TC | 28 passed / 3 remote pending / 31 total |
| 构建产物 | gateway + SDK，各 1 wheel + 1 sdist |
| Twine metadata | 4/4 passed |
| 依赖审计 | No known vulnerabilities found |
| Compose | development + production config passed |
| Docker runtime | sidecar + 双副本 gateway 全部 healthy/ready，已清理 |
| Diff check | passed，无空白错误 |

唯一 skipped 为项目既有条件性测试；13 条 warning 为既有 Starlette TestClient 弃用提示、缺省 gRPC circuit breaker 建议和旧 detector 配置格式弃用提示，没有新增失败或未处置安全告警。

## 2. 质量门证据

### 2.1 自动化与覆盖率

最终等价 CI 命令同时执行主测试集和两个示例插件测试集：

```text
pytest tests/ examples/plugins/python-inprocess/tests examples/plugins/python-grpc/tests
  --cov=src/z_llm_safety_gateway --cov-fail-under=90
```

结果：904 passed / 1 skipped，92.85%。示例 gRPC sidecar 的 API key mismatch 路径也已纳入正式门禁。

### 2.2 多版本状态

| Python | 状态 | 说明 |
|--------|------|------|
| 3.10 | PASS | 本地完整 pytest/coverage/Ruff/Mypy/build/Docker |
| 3.11 | PENDING REMOTE | 本机无解释器；Gate 3 后由 CI matrix 验证 |
| 3.12 | PENDING REMOTE | 本机无解释器；Gate 3 后由 CI matrix 验证，build/release job 使用 3.12 |

包元数据已收紧为 `>=3.10,<3.13`，与支持矩阵一致。

### 2.3 构建、安装与审计

- 最终重建两个 wheel 和两个 sdist，Twine 4/4 通过。
- Phase 4 的干净安装验证已运行三个 CLI；Phase 5 最终重建四个产物，并由 workflow 契约锁定三个入口冒烟步骤。
- SDK 独立 wheel 在无 gateway 包的临时环境中通过。
- `pip-audit --local --skip-editable` 对已解析环境返回 `No known vulnerabilities found`；editable 的两个本项目包按工具规则跳过，依赖均已审计。
- benchmark 最终复跑：P50 0.17ms、P95 0.25ms、P99 0.31ms、5258 req/s；均优于设计建议阈值，报告写入临时目录，不覆盖 tracked 发布报告。

## 3. 生产运行态证据

生产 Compose 不再引用不存在的 sidecar 镜像，而是构建仓库内 Python gRPC 示例；gateway 镜像安装 `[grpc]` runtime，并在 sidecar `service_healthy` 后启动。

| 目标 | `/health` | `/ready` | Detector 状态 |
|------|-----------|----------|-----------------|
| gateway-1 / 8080 | healthy | ready | 3 configured / 3 loaded / 3 healthy / degraded=false |
| gateway-2 / 8081 | healthy | ready | 3 configured / 3 loaded / 3 healthy / degraded=false |
| acme-guard | healthy | gRPC serving | 示例测试另行验证 `DETECTOR_API_KEY` mismatch 会拒绝初始化 |

双副本使用 `8080-8081:8080` 主机端口范围；审计写入 `/var/log/safety-gateway` 持久卷。验证完成后，隔离项目 `zlgverify20260821` 的容器、网络和卷全部删除，`docker compose ps --all` 为空。

## 4. 三路技术评审

| 评审 | 初始结果 | 主要发现 | 最终处置 |
|------|----------|----------|----------|
| 代码/安全 | C0/H2/M2/L1 | Release 未依赖质量矩阵；生产镜像缺 gRPC；Python 上界/TLS 等 | 全部修复或校正文档 |
| 测试/配置 | C0/H3/M2/L1 | 16 个 stale checkpoint；Compose 启动竞态/端口/密钥；归档后测试失效 | 全部新增契约并修复 |
| 文档/Skills | C0/H5/M5/L2 | 安全配置字段漂移、mTLS 误述、不可用安装渠道、Verify 12/11 矛盾 | 文档与渠道校正；第 12 类独立 L3 检查 |

逐文件复核覆盖 workflow、包元数据、SDK、Compose/Docker、文档/治理、STDD 资产、测试和工具脚本。最终本地残留为 C0/H0/M0/L0；远程必需项单独列在第 8 节。

## 5. 十二类失败模式检查

vendored v2.9.5 Verify 正文定义 a-k 11 类，但入口宣称 12 类。本 change 保持上游文件哈希不变，并把第 12 类明确执行为 `(l) 锚定缺失`。

| 类别 | 最终结果 | 证据 |
|------|----------|------|
| (a) 幻觉行为 | PASS | Markdown 链接/锚点、workflow、Compose、31 个 checkpoint 路径均验证；无 `ZLG_` 虚构覆盖机制 |
| (b) 范围蔓延 | PASS | 额外 Docker/SDK/docs 修复均直接来自发布、部署和文档 capability 的 Verify 阻塞项 |
| (c) 级联错误 | PASS | gRPC 能力缺失不再被 liveness 假绿掩盖；Release 任一 quality/build/audit 失败均阻断 |
| (d) 上下文丢失 | PASS | checkpoint 测试兼容 active/archive；CLI status 测试不再绑定当前 phase |
| (e) 工具误用 | PASS | 无 destructive Git；Docker 资源使用独立项目名并完整清理；Gate 3 前无远程写入 |
| (f) 运行时行为偏差 | PASS | 双副本实际 `/health`、`/ready`、3/3 detectors 和 sidecar auth 均执行 |
| (g) 管线断链 | PASS | tag → quality/build/audit → Release；config → image extra → sidecar healthy → detector ready 链路完整 |
| (h) 内容质量偏差 | PASS | 配置、TLS、安装、审计路径、版本和插件文档经独立评审与契约检查 |
| (i) 指令衰减 | PASS | Gate 1/2 明确确认；Phase 4 严格 RED→GREEN→REFACTOR；Gate 3 未自动越过 |
| (j) 覆盖真空 | PASS | 8 capabilities 均有自动化；agent_spec node 通过 AST 元契约；示例插件测试进入 CI |
| (k) 契约断层 | PASS | docs/runtime 配置字段、Compose secret/env、SDK Release wheel、Release needs 一致 |
| (l) 锚定缺失 | PASS | 两个 L3 reference change 均存在；D1-D11 与本次调整逐项比对，偏离写入 adjustments |

## 6. L3 锚定检查

- `archive/2026-08-15-v0.1.0-production-ready` 存在，提供发布、Compose、CI 与文档基线。
- `archive/2026-08-19-detector-readiness-fail-safe` 存在，提交 `33437bd` 已作为当前基线前置提交。
- 官方 STDD v2.9.5 固定 commit、MIT notice、37 项源码 manifest 与额外文件拒绝检查均通过。
- 本轮设计偏离已全部写入 `design-adjustments.yaml/.md`，无需重新 Spec。

## 7. 经验库

本轮按 Verify 规范新增 4 条真实 `discovered` 经验：

| ID | 类别 | 模式 |
|----|------|------|
| EXP-2026-0004 | (g) 管线断链 | Tag 发布必须依赖同一提交的完整质量矩阵 |
| EXP-2026-0005 | (k) 契约断层 | 安全配置文档示例必须由运行时模型反向校验 |
| EXP-2026-0006 | (j) 覆盖真空 | checkpoint 必须引用真实且归档后仍可定位的节点 |
| EXP-2026-0007 | (f) 运行时偏差 | 生产配置启用能力时镜像依赖和 readiness 必须验证该能力 |

四条均 occurrences=1、lifecycle=discovered。未伪造 occurrence，未执行 verify/deposit/share。

## 8. Gate 3 后待完成

| TC | 远程动作 | 当前状态 |
|----|----------|----------|
| TC-GOV-003 | 启用 private vulnerability reporting；创建 `dependencies` label；创建 v0.1.1/v0.2.0 milestones | PENDING |
| TC-GH-004 | push 后验证 Python 3.10/3.11/3.12 quality、build、audit | PENDING |
| TC-REL-007 | 创建并 push `v0.1.1` tag；验证 GitHub Release 和四个产物 | PENDING |

这些动作具有外部可见或难撤回状态，严格保留到用户明确确认 Gate 3 后。

## 9. Gate 3 建议

Gate 3 已由用户于 2026-08-21 11:04 +08:00 明确确认，Phase 6 Deliver 已启动。按顺序执行：本地提交 → push main → 远程治理补齐 → 验证 CI → 创建并 push tag → 验证 Release 四产物 → 归档 change。
