# Codex-only STDD 本地适配任务

## Slice 1 — Codex 项目入口与旧适配清理（P0）

- [x] RED：新增 TC-CODEX-001～005 的项目契约测试并确认失败
- [x] GREEN：创建七个 `.agents/skills/stdd-*/SKILL.md` 薄入口
- [x] GREEN：更新 `AGENTS.md` 与长程权限说明为 Codex 原生边界
- [x] GREEN：删除活跃的 Trae、Claude Code、WorkBuddy 适配副本
- [x] VERIFY：运行本切片测试及 vendored manifest 契约测试
- [x] REFACTOR：复核入口单一来源、失败显式及删除范围

## Slice 2 — 活跃 overlay 一致性与质量门（P1）

- [x] RED：新增 TC-CODEX-007 活跃文档 Codex-only 契约并确认失败
- [x] GREEN：更新 `STDD.md` 与 upgrade Skill 的活跃平台说明
- [x] VERIFY：运行 TC-CODEX-007、Skill validator、Ruff、Mypy、完整 pytest
- [x] REFACTOR：检查文档边界、Git diff 和四项原则

## Gate 3 前

- [x] 三路并行审查：实现、测试/配置、文档/Skill
- [x] 完成 12 类失败模式检查
- [x] 生成设计偏差与测试报告
- [ ] 停在 Gate 3 等待用户确认
