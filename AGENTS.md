# AGENTS.md — z LLM Safety Gateway 项目记忆文件

> **STDD 强制门已启用**：本项目使用 STDD (Spec+Test Driven Development) 流程。修改代码前必须先走 STDD 流程（/stdd-understand）。
> 如果项目未启动 STDD change 而收到代码修改请求，请提示用户先启动 STDD 流程。

## 项目概述

z LLM Safety Gateway 是一个开源、模块化的 LLM 内容安全网关，作为应用程序与 LLM 提供商之间的透明代理，执行实时内容安全检测和过滤。

- **技术栈**: Python 3.12+ / FastAPI / Pydantic v2 / httpx / structlog
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
  platforms/trae/       # Trae 平台适配
changes/                # 活跃变更
specs/                  # 主规范（变更完成后合并）
archive/                # 已完成变更
.trae/skills/           # Trae skill 文件（/stdd-xxx 命令）
```

## 常用命令

| 命令 | 用途 |
|------|------|
| `/stdd-understand <需求>` | Phase 1: 启动新变更需求理解 |
| `/stdd-spec` | Phase 2: 进入规格设计 |
| `/stdd-continue` | 继续执行当前变更（Phase 3-6） |
| `python3 <stdd_path>/bin/stdd status` | 查看变更状态 |

## 开发约定

- 所有代码变更通过 STDD 流程：Understand → Spec → Slice → Build → Verify → Deliver
- 严格 TDD：RED（写失败测试）→ GREEN（最小实现）→ REFACTOR（重构）
- Python 代码遵循 `.stdd/standards/python.md` 规范
- 测试框架: pytest + pytest-asyncio
- Lint: ruff
- 类型检查: mypy
- DESIGN.md 是项目级 master spec，每个 STDD 变更从中提取相关需求

## 开发阶段（对应 STDD 变更）

| 变更 | 版本 | 内容 | 预计工期 |
|------|------|------|---------|
| v0.1.0 | Framework Skeleton | FastAPI server, Config, Provider proxy, Content extractor | 2-3 days |
| v0.2.0 | Pipeline & Detectors | Pipeline engine, 5 MVP detectors, Circuit breaker | 3-4 days |
| v0.3.0 | Streaming & Audit | SSE streaming, Sliding window, Post-audit, Recall, Audit log | 3-4 days |
| v0.4.0 | Security & Observability | Auth, Rate limit, TLS, Prometheus, OpenTelemetry | 2-3 days |
| v0.5.0 | Plugin Ecosystem | gRPC sidecar, Plugin loader, Detector SDK | 3-4 days |
| v1.0.0 | Production Ready | Documentation, Test coverage, Docker Compose, CI | 2-3 days |

## STDD 强制性约束

| # | 规则 |
|---|------|
| 1 | 绝不可跳过 Gate 确认 — 三道 Gate（Phase 1/2/5）必须用户明确确认 |
| 2 | 绝不静默修改设计 — 偏离必须记录到 design-adjustments.md |
| 3 | 绝不可先写代码再补测试 — 严格 RED→GREEN→REFACTOR |
| 4 | 绝不可跳过失败模式检查 — Phase 5 必须全量检查 |
| 5 | 绝不可跳过切片验证 — 每个切片必须通过验证 |
