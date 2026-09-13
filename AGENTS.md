# AGENTS.md — z LLM Safety Gateway 项目记忆文件

> **STDD 强制门已启用**：本项目使用 STDD (Spec+Test Driven Development) 流程。修改代码前必须先走 STDD 流程（`$stdd-understand`）。
> 如果项目未启动 STDD change 而收到代码修改请求，请提示用户先启动 STDD 流程。
>
> **四项项目原则是所有工作的前置约束**：开始需求分析、规格设计、切片、实现、验证或架构决策前，必须完整阅读 `PRINCIPLES.md`，并逐项检查当前工作是否符合。若原则之间存在取舍，必须显式记录；不得静默偏离。

## 项目原则（强制检查）

权威正文及检查问题见 `PRINCIPLES.md`。以下四项适用于每一次变更和决策：

1. **能力插件化，执行 Flow 化，核心保持最小**
2. **策略必须显式，失败绝不静默**
3. **边界保持透明，契约保持稳定**
4. **每一个安全决定都有证据，数据默认受到保护**

每个 STDD change 的需求理解、设计与验证结论都必须逐项回答 `PRINCIPLES.md` 中的 Required Principle Check；不适用的项目也必须简述理由。

## 项目概述

z LLM Safety Gateway 是一个开源、模块化的 LLM 内容安全网关，作为应用程序与 LLM 提供商之间的透明代理，执行实时内容安全检测和过滤。

- **技术栈**: Python 3.10–3.12（推荐 3.12）/ FastAPI / Pydantic v2 / httpx / structlog
- **源码目录**: `src/`
- **测试目录**: `tests/`
- **主设计文档**: `DESIGN.md`（项目级 master spec，60 条设计决策）
- **许可证**: Apache 2.0

## STDD 目录结构

```
.stdd/                  # STDD 核心系统
  skills/               # 6 个阶段 Skill 文件
  templates/            # 文档模板
  standards/            # 开发规范（python.md）
  config.d/             # 模块化配置
changes/                # 活跃变更
specs/                  # 主规范（变更完成后合并）
archive/                # 已完成变更
.agents/skills/         # Codex 项目级 STDD Skill 薄入口
```

## 常用命令

| 命令 | 用途 |
|------|------|
| `$stdd-understand <需求>` | Phase 1: 启动新变更需求理解 |
| `$stdd-spec` | Phase 2: 进入规格设计 |
| `$stdd-slice` / `$stdd-build` / `$stdd-verify` | 继续 Phase 3–5 |
| `$stdd-deliver` | Gate 3 确认后执行 Phase 6 |
| `$stdd-upgrade` | 校验或升级项目级 STDD overlay |
| `python3 <stdd_path>/bin/stdd status` | 查看变更状态 |

## 开发约定

- 所有代码变更通过 STDD 流程：Understand → Spec → Slice → Build → Verify → Deliver
- 严格 TDD：RED（写失败测试）→ GREEN（最小实现）→ REFACTOR（重构）
- Python 代码遵循 `.stdd/standards/python.md` 规范
- 测试框架: pytest + pytest-asyncio
- Lint: ruff
- 类型检查: mypy
- DESIGN.md 是项目级 master spec，每个 STDD 变更从中提取相关需求
- PRINCIPLES.md 是项目级最高设计约束，每次变更和决策必须逐项检查

## 开发阶段与公开 Roadmap

`DESIGN.md` 的 `Post-v0.1.0 Roadmap` 是版本路线的唯一权威来源；本表只保留开发记忆摘要。

| 变更 | 版本 | 内容 | 状态 |
|------|------|------|---------|
| v0.0.1 | Framework Skeleton | FastAPI server, Config, Provider proxy, Content extractor | 已完成 |
| v0.0.2 | Pipeline & Detectors | Pipeline engine, 5 MVP detectors, Circuit breaker | 已完成 |
| v0.0.3 | Streaming & Audit | SSE streaming, Sliding window, Post-audit, Recall, Audit log | 已完成 |
| v0.0.4 | Security & Observability | Auth, Rate limit, TLS, Prometheus, OpenTelemetry | 已完成 |
| v0.0.5 | Plugin Ecosystem | gRPC sidecar, Plugin loader, Detector SDK | 已完成 |
| v0.1.0 | First Public Test Release | Documentation, Test coverage, Docker Compose, CI | 已完成 |
| v0.2.0 | Flow Foundation | Flow contracts, runtime, policy, evidence and compatibility | 已完成 |
| v0.3.0 | Multi-tenant Safety Policy Isolation | 四个独立 STDD changes，详见 DESIGN 权威 Roadmap | 进行中：changes 1/4、2/4、3/4 delivered；change 4/4 pending |

## STDD 强制性约束

| # | 规则 |
|---|------|
| 1 | 绝不可跳过 Gate 确认 — 三道 Gate（Phase 1/2/5）必须用户明确确认 |
| 2 | 绝不静默修改设计 — 偏离必须记录到 design-adjustments.md |
| 3 | 绝不可先写代码再补测试 — 严格 RED→GREEN→REFACTOR |
| 4 | 绝不可跳过失败模式检查 — Phase 5 必须全量检查 |
| 5 | 绝不可跳过切片验证 — 每个切片必须通过验证 |
