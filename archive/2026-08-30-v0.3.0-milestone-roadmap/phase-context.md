# Phase Context — 2026-08-30-v0.3.0-milestone-roadmap

---

## Phase 1: UNDERSTAND (completed 2026-08-30T12:48:26+08:00)

### 关键决策

- 需求边界：本 change 只定义公共 v0.3.0 范围并统一 Roadmap，不实现运行时能力。
- 里程碑主题：多租户安全策略隔离基础。
- 模式建议：documentation / standard，保留全部三道 Gate。

### 用户关注点

- 用户要求按既定方向启动 v0.3.0 里程碑范围定义与 Roadmap 统一。
- Gate 1 已明确确认提案，无附加调整。

### 被否决的方向

- 直接实现多租户：必须先完成 Roadmap 范围契约，再分别启动实施 change。
- 把 Provider、多模态、OAuth 一并纳入 v0.3.0：范围和安全边界过宽。

### 产出物清单

- `proposal.md` / canonical proposal — Gate 1 confirmed。

## Phase 2: SPEC (completed 2026-08-30T16:32:52+08:00)

### 关键技术决策

- DESIGN Post-v0.1.0 Roadmap 是唯一权威来源；README/CHANGELOG/AGENTS 仅保留有界摘要。
- v0.3 引用使用 completed、in-scope、deferred、immutable-history 四类语义。
- 公共 v0.3.0 由四个独立 STDD changes 交付，全部完成后才可进入发布。
- 延后候选不擅自分配新目标版本。
- 使用现有 documentation contract 测试做持久化验证，不修改 runtime。

### 经验触发记录

- EXP-2026-0019：发布状态不能压平，纳入 SC-RMAP-004 / TC-RMAP-004。
- EXP-2026-0022：TC-ID 全局唯一且绑定真实 checkpoint，纳入所有 agent specs。

### 已知坑点 / 注意事项

- `extract-proposal` 对生成的 Human View 丢失 Capability 标题；Phase 2 使用 canonical proposal，
  本 change 不修复工具链。
- 现有 `test_design_roadmap_matches_release_history` 精确要求旧 v0.3.0 占位文本，Phase 4 必须
  先更新断言形成 RED，再修改文档进入 GREEN。
- 历史 archive/canonical/spec/Release Notes 不得批量替换。

### 未解决问题（待 Phase 4 验证）

- 候选引用分类扫描既要覆盖当前表面，又不能把历史引用当作待改内容；用显式集合和 Git diff
  边界双重验证。
- 文档任务允许修改文档契约测试，但产品 runtime、配置、API 和版本表面必须零变化。

### 产出物清单

- `design.md` — Gate 2 confirmed。
- `specs/milestone-scope-governance/spec.md` — 8 Scenarios。
- `specs/project-docs/spec.md` — 4 Scenarios。
- `canonical/specs/agent/*.yaml` — 8 checkpoints。
- `test-plan.md` — 12 TC-ID。

## Phase 5: VERIFY (completed 2026-08-30T17:20:57+08:00)

### 验证结论

- 三轮并行 review 完成，最终 C0/H0/M0/L0。
- 主质量门 1090 passed / 1 skipped，coverage 93.34%；Ruff、Mypy、git diff check 通过。
- Python 3.10、3.11、3.12 正式 coverage 矩阵均通过。
- 12/12 TC、8 个 canonical actions 和 12 个 checkpoint targets 全部通过。
- 十二类失败模式全部检查，无未解决项；设计调整 1 项，不要求重新 Spec/Build。
- E2E 按 `quality.e2e.enabled: false` 跳过。

### 下一步

- 等待用户确认 Gate 3；确认前不进入 Deliver，不执行 Git 交付。

### 已知后续项

- 活跃 runtime 注释和两个 legacy config tests 仍保留内部 `v0.3.0` 标签，已显式分类并受迁移期
  契约保护；建议由独立 STDD cleanup change 或首个 v0.3.0 实施 change 清理。

## Phase 4: BUILD (completed 2026-08-30T16:57:31+08:00)

### S1：权威范围与候选分类（completed 2026-08-30T16:51:19+08:00）

- TC 覆盖：5/5；新增测试：5。
- RED：5 个新契约测试全部失败，证明旧 Roadmap 缺少权威、范围、拆分和分类。
- GREEN：聚焦测试 5/5、documentation contract 14/14。
- 全量回归：正式 coverage 命令 1082 passed / 1 skipped，coverage 93.34%。
- 非插桩首次回归的 TC-PE-003 命中已知 EXP-2026-0011 主机微基准模式；未修改性能门，
  使用 CI 同构 coverage 命令取得可信功能回归证据。
- 修改：`DESIGN.md`、`AGENTS.md`、`tests/unit/release/test_documentation_contract.py`。

### 上下文与经验

- Context budget：phase-context 新鲜、当前状态完整，继续执行。
- verified/settled 经验：0；主动采用 discovered EXP-2026-0019、EXP-2026-0022，S1 另命中
  EXP-2026-0011。

### S2：次级文档同步与历史保护（completed 2026-08-30T16:54:29+08:00）

- TC 覆盖：5/5；新增测试：5。
- RED：3 failed / 2 direct GREEN；直接通过的发布历史与 immutable-history 场景已有 S1/既有
  契约等价证据。
- GREEN：聚焦测试 5/5、documentation contract 19/19。
- 全量回归：1087 passed / 1 skipped，coverage 93.34%。
- 修改：`README.md`、`CHANGELOG.md`、`tests/unit/release/test_documentation_contract.py`。

### S3：产品边界与全量回归（completed 2026-08-30T16:57:31+08:00）

- TC 覆盖：2/2；新增测试：2。
- RED：1 failed / 1 direct GREEN；链接与负向声明已有基础保护，新增持久化 TC。
- GREEN：聚焦测试 2/2、documentation contract 21/21。
- Checkpoints：12 个新 pytest nodes collect 成功；TC-ID 在 tests/ 中各出现一次。
- 全量回归：1089 passed / 1 skipped，coverage 93.34%。
- Ruff：通过；Mypy：99 source files / 0 issues；`git diff --check`：通过。
- 最终产品 diff 仅含 AGENTS、CHANGELOG、DESIGN、README 和 documentation contract test。

### Phase 4 结论

- 三个切片全部完成，TC 12/12；新增测试 12。
- 没有设计偏离；未修改 runtime、config、API、package version 或历史材料。
- 下一步：Phase 5 VERIFY 全量质量门、失败模式检查和 Gate 3 材料。

## Phase 6: DELIVER（completed 2026-08-30T21:28:32+08:00）

### 已完成

- Gate 3 已于 2026-08-30T20:43:12+08:00 确认。
- change 已归档到 `archive/2026-08-30-v0.3.0-milestone-roadmap/`。
- canonical proposal、2 份 agent specs、2 份 Human View specs 和代码结构摘要已合并。
- 本 change 无 deposited experience，社区上传跳过。
- 归档后发现并修复 DA-002 累积 spec 生命周期契约问题。
- 交付后复验：documentation contract 22/22、canonical actions 8/8、全量 1090 passed /
  1 skipped、coverage 93.34%、Ruff/Mypy/diff check 全部通过。

### Git 交付

- 用户已明确授权 commit、tag 和 push。
- Commit：`docs(roadmap): define v0.3.0 milestone scope`。
- 非发布 tag：`stdd-v0.3.0-roadmap-2026-08-30`。
- 推送目标：`origin/main` 及上述 tag。
