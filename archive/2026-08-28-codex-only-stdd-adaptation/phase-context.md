# Phase Context — 2026-08-28-codex-only-stdd-adaptation

## Phase 1: UNDERSTAND (completed 2026-08-28T14:14:18+08:00)

### 关键决策

- 当前项目只保留 Codex 活跃适配，非 Codex 平台副本退出维护范围。
- Gateway、SDK 和产品 roadmap 不属于本 change；roadmap 候选另记在 `potential-requirements.md`。

### 用户关注点

- 用户明确要求本地环境只匹配 Codex，不再匹配 Claude Code 和 Trae。
- 用户要求按 roadmap 记录下一步工作，但不与本配置 change 混合实现。

### 产出物清单

- `proposal.md` — Gate 1 已确认。
- `potential-requirements.md` — 后续 roadmap 候选，非本次实现范围。

## Phase 2: SPEC (completed 2026-08-28T14:24:32+08:00)

### 关键技术决策

- 使用项目 overlay 而不 fork vendored STDD CLI，保持上游 SHA-256 来源证据。
- 使用七个薄 Codex Skill 入口引用 `.stdd/skills` 单一正文，不复制、不使用 symlink。
- 删除活跃非 Codex 平台副本，但保留 archive 与 vendored CLI 历史/来源。
- Codex 权限由运行环境管理，不创建 `.claude/settings.local.json` 或修改 `~/.codex`。

### 经验触发记录

- EXP-2026-0005：配置文档需要契约测试，纳入 SC-STDD-002。
- EXP-2026-0006：Agent checkpoint 必须引用真实测试节点，纳入全部 CP 命名与 Phase 5 收集验证。
- EXP-2026-0017：失败不能被后续成功掩盖，质量门使用独立非零退出断言。

### 已知坑点 / 注意事项

- Codex 通常在新 session 扫描项目 Skills；当前 session 只能验证结构，交付时需新 session 冒烟。
- vendored CLI 仍可能显示通用平台安装帮助；它不是项目活跃 overlay，不得为此修改 hash 快照。
- STDD v2.9.5 Gate 2 顺序检查错误地从 `phases.phases.*` 查找前序确认；使用 gates.yaml 已支持的文件 token 同步对话确认，不修改 vendored CLI。

### 产出物清单

- `design.md` — Gate 2 已确认。
- `specs/codex-stdd-adapter/spec.md` — 5 个 Scenario。
- `specs/stdd-platform-installation/spec.md` — 3 个 Scenario。
- `canonical/specs/agent/*.yaml` — 8 个验证检查点。
- `test-plan.md` — 8 个 TC-ID。

## Phase 3: SLICE (completed 2026-08-28T14:43:00+08:00)

### 关键决策

- 两个串行切片：先建立 Codex 入口与清理契约，再收敛活跃文档和质量门。
- 每个切片都有独立 RED 证据；vendored CLI 只由既有 manifest 契约保护。

## Phase 4: BUILD (completed 2026-08-28T14:48:30+08:00)

### TDD 证据

- S1：5 个新增节点在实现前全部失败，最小实现后 6/6（含 manifest）通过。
- S2：活跃文档扫描在更新前失败，更新后 7/7 change 契约通过。
- 7 个 Codex Skill 入口均通过 quick validator。
- 无覆盖率运行命中已有主机敏感吞吐微基准失败；该失败与纯配置 diff 无执行路径交集，保留到 Phase 5 使用 release coverage 命令复核。

## Current: Phase 5 VERIFY in progress

### 下一步

- 处理三路并行审查 finding，执行完整质量门和十二类失败模式检查，生成 Gate 3 材料。
