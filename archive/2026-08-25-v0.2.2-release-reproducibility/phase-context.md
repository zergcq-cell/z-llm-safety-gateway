# Phase Context — 2026-08-25-v0.2.2-release-reproducibility

> 阶段交接摘要。冲突时以各 Phase 的正式产出物为准。

---

## Phase 1: UNDERSTAND (completed 2026-08-25T20:51:08+08:00)

### 关键决策

- **需求边界确定**：v0.2.2 只强化发布可复现性、draft-first 状态机、确定性校验、证据输出与版本文档，不修改运行时行为。
- **版本角色确定**：Gateway 目标版本为 `0.2.2`；Detector SDK 保持 `0.1.1`，API 不变。
- **公开资产契约确定**：Release 仍精确包含四个 distribution；evidence 只作为保留 90 天的 Actions artifact。

### 用户关注点

- 用户确认采用 thorough 模式，并要求按 STDD 完整推进 v0.2.2。
- 既有公开 tag、peeled commit 和 Release 状态不可删除、移动、覆盖或静默改变。

### 被否决的方向

- K8s、Redis、新 Provider、UI、新检测器、PyPI、容器注册表、SBOM、签名及 Detector SDK 升版均超出范围。
- 不采用第五个 Release asset，不在验证失败时自动删除或复用 draft。

### 产出物清单

- `proposal.md` — Gate 1 已确认，confirmed_at: `2026-08-25T20:51:08+08:00`
- `canonical/proposals/2026-08-25-v0.2.2-release-reproducibility.yaml`

### 完整上下文文件清单

- `proposal.md`：需求背景、能力列表、约束、风险和成功标准。
- `canonical/proposals/2026-08-25-v0.2.2-release-reproducibility.yaml`：结构化提案。

---

## Phase 2: SPEC (completed 2026-08-25T21:37:00+08:00)

### 关键技术决策

- 四个官方 Actions 升级到已核验的 Node 24 版本，并固定完整 commit SHA。
- 使用 `pip-tools==7.6.1` 生成带完整 hashes 的 release-tools lock；运行时固定 `pip==26.2.1`、`build==1.5.0`、`twine==7.0.0`、`pip-audit==2.10.1`、`hatchling==1.32.0`，构建使用 `--no-isolation`。
- tag 发布采用“明确 404 → 私有 draft → 精确校验 → publish → 公开状态复检”的状态机；失败 draft 保持私有供诊断，公开 tag 永不自动重写。
- Release 校验覆盖 notes、精确四资产、SHA-256 digest、draft/prerelease 状态和 peeled tag SHA；网络采集与纯确定性判断分离。
- Evidence 仅记录公开元数据，作为 90 天 Actions artifact 和 Job Summary，不进入 Release assets。
- workflow 权限保持最小：顶层 `contents: read`，仅 tag release job 获得 `contents: write`；`workflow_dispatch` 只验证、不发布。

### 经验触发记录

- `EXP-2026-0004`–`EXP-2026-0006`：用于约束真实构建、检查点可执行性和远程发布证据。
- `EXP-2026-0014`–`EXP-2026-0016`：用于约束 clean-install 证据、远程错误分类及 Release 精确校验。

### 已知坑点 / 注意事项

- hash lock 不能手工拼接，必须由固定生成器在干净 Python 3.12 环境中生成并审查。
- GitHub API 的 digest 缺失、认证失败、限流、网络错误或 5xx 均必须硬失败，只有结构化明确 404 可表示不存在。
- draft 校验失败会留下私有状态，需要维护者显式诊断和处置；workflow 不自动清理。
- evidence 上传发生在公开复检后；若上传失败 workflow 为红，但不得自动回滚已验证的公开 tag/Release。

### 未解决问题（待 Phase 4/5 验证）

- 固定工具版本的完整传递依赖与 hashes 需在 Phase 4 通过受控生成流程落地。
- Node 24 Actions 的三种事件路径、GitHub draft/public 状态和远程 evidence 需由 Phase 5 本地契约及后续远程验收共同证明。

### 产出物清单

- `design.md` — Gate 2 已确认。
- `specs/*/spec.md` — 3 个 Capability、8 个 Requirements、15 个 Scenarios。
- `canonical/specs/code/` — 3 份代码行为规格。
- `canonical/specs/agent/` — 3 份 Agent 验证规格。
- `test-plan.md` — 15 个 TC；P0 12 个、P1 3 个。

### 完整上下文文件清单

- `design.md`：技术锚点、8 项决策、架构、失败路径和风险取舍。
- `specs/release-hardening/spec.md`：可复现工具链、draft-first、Release 校验与 evidence 行为。
- `specs/github-setup/spec.md`：Node 24 Actions、完整 SHA、事件与权限边界。
- `specs/project-docs/spec.md`：Gateway/SDK 独立版本、历史和路线图口径。
- `test-plan.md`：TC-ID 映射、执行矩阵和回归风险。

---

## Phase 3: SLICE (completed 2026-08-25T21:44:43+08:00)

### 切片方案

- S1（P0 · 并行组 1）：Release lock 与 Node 24 Action 锚点 — 3 个 TC。
- S2（P0/P1 · 并行组 1）：Release 校验器与 evidence — 5 个 TC。
- S3（P0/P1 · 并行组 1）：Gateway/SDK 版本与路线图 — 3 个 TC。
- S4（P0/P1 · 并行组 2）：Draft-first workflow 集成 — 4 个 TC，依赖 S1～S3。

### 风险提示

- S1/S2/S4 均为高风险发布供应链切片；S3 为中风险角色化版本表面切片。
- CLI 图为 0 条依赖、0 个循环；手工依赖只用于避免在输入和纯校验器稳定前接线公开发布状态机。

### 产出物清单

- `slices.md` — 4 个切片、15 个 TC、依赖与风险均已标注。
- `tasks.md` — Phase 4 和 Phase 5 的可核对任务清单。

---

## Phase 4: BUILD (completed 2026-08-25T22:26:43+08:00)

### 切片完成状态

| Slice | TC 覆盖 | 新增测试 | 状态 |
|-------|---------|---------:|:----:|
| S1 Release lock / Node 24 | 3/3 | 3 | ✅ |
| S2 Validator / evidence | 5/5 | 18 cases | ✅ |
| S3 Versions / docs | 3/3 | 2 new functions | ✅ |
| S4 Draft-first workflow | 4/4 | 4 new functions | ✅ |

### S1 实现记录

- 新增 `requirements/release-tools.in`、`requirements/release-tools.lock`、`requirements/README.md`。
- CI/Release 的四类官方 Actions 已改为已核验 Node 24 完整 SHA。
- Python 3.12 `--require-hashes` 安装完整 lock 成功；完整回归为 1030 passed、1 skipped。
- 记录 `ADJ-001`：为确保 `pip==26.2.1` 进入 lock，生成命令增加 `--allow-unsafe --strip-extras`。

### S2 实现记录

- `tools/release_checks.py` 已支持 exact draft/public 状态、uploaded/digest/size、peeled SHA 与稳定错误。
- absence 解析只接受结构化 404；认证、限流、服务、网络或无效 JSON 均显式失败。
- schema v1 evidence 采用字段白名单、稳定排序、notes SHA-256 和外部 verified SHA，不传播 token、headers 或 actor email。
- 18 个新增参数化测试全部通过；完整回归为 1048 passed、1 skipped，Ruff/Mypy 通过。

### S3 实现记录

- Gateway package/runtime、README、指南、配置与 production Compose 已更新到 0.2.2。
- Detector SDK package/runtime、wheel URL 和示例依赖保持 0.1.1；README 增加精确兼容矩阵。
- CHANGELOG 新增隔离的 v0.2.2 维护说明；v0.2.0/v0.2.1 正文由负向契约保护。
- DESIGN 路线图区分 v0.2.0 tag 成功 / Release 失败、v0.2.1 Release 成功与 v0.2.2 当前 release candidate，v0.3.0 明确需独立 STDD change。
- 完整回归为 1050 passed、1 skipped；Ruff 和 99 个 Mypy source files 全部通过。

### S4 实现记录

- Release build/audit 共用 hash lock，Gateway 与 SDK 均以 `--no-isolation` 构建。
- tag-only 状态机已实现：明确 404 → 私有 draft → exact payload/ref 校验 → publish → public recheck。
- 发布失败不包含任何自动 tag 删除、移动、draft 复用或自动清理路径。
- evidence 仅在公开复检通过后生成，上传为 90 天 Actions artifact，并写入非敏感 Job Summary。
- 19 个本地 Agent checkpoint 已通过 AST、collect-only 与执行验证；3 个远程 checkpoint 明确留在 Gate 3 后按 pre-tag、annotations、release 三个时点执行。
- 真实构建得到 Gateway 0.2.2 / SDK 0.1.1 四产物且 Twine 通过；完整回归 1054 passed、1 skipped。

### Phase 4 设计偏离汇总

- `ADJ-001`（minor）：锁生成命令增加 `--allow-unsafe --strip-extras`，以满足 pip hash pin；行为契约未改变。

---

## Phase 5: VERIFY (completed 2026-08-26T07:28:07+08:00)

### 最终质量门

- 三轮、每轮三路只读技术评审完成，所有本地发现均已修复并复审，无未解决 C/H/M/L 问题。
- Python 3.10 与 3.12 均为 1065 passed、1 skipped；Python 3.11 本机无解释器，明确留给同 SHA CI。
- Coverage 93%；Ruff 通过；Mypy 99 个源码文件 0 issues；diff check 与 14 个 YAML 解析均通过。
- Gateway 0.2.2 / SDK 0.1.1 四产物构建与 Twine 通过；Python 3.12 hash lock 安装通过。
- 15/15 TC 有自动化映射：13 个本地 TC PASS；TC-GH-011、TC-REL-025 待远程，未提前标为 PASS。
- 19 个本地 checkpoint nodes 已通过 AST、collect-only 与实际执行；3 个远程 checkpoint 为 pre-tag、annotations、release。
- 十二类失败模式均完成；(f) 真实 GitHub 运行时行为和 (l) 历史远程不变性保持待远程。
- 新增 EXP-2026-0017～0020，复用 EXP-0004/0006/0014/0015/0016；经验库共 20 条。
- ADJ-001～003 均 resolved，无需重新 Spec 或 Build；四项项目原则复核通过。

### Gate 3 状态

- `test-report.md` 和 `design-adjustments.md` 已生成。
- Verify 已完成，Gate 3 已于 2026-08-26T07:51:13+08:00 获得用户明确确认。
- 三份 human specs、六份 canonical specs 与代码结构索引已合并，change 已归档。
- Deliver 正按 push main → same-SHA CI → dry-run → pre-tag absence → annotated tag → tag workflow → annotations/release evidence 顺序执行。

## Phase 6 Deliver 远程迭代

- Attempt 1：提交 `58e9ff48e9d447f9cf8539d3e0eb00cbb31529c8` 的 main CI 三版本全绿。
- Dry-run `32913194675` 在 build/audit 的 hash lock 安装阶段失败关闭；release job skipped，未创建 tag 或 Release。
- 根因：macOS 生成 lock 时，keyring 的 Linux 条件依赖 `SecretStorage>=3.2` 被排除。
- 修复：先增加失败契约测试，再把 `secretstorage==3.5.0` 作为跨平台直接输入，使用固定 pip-tools 7.6.1 / Python 3.12 重新生成完整 hashes。
- 本地证据：目标测试 GREEN；全新 Python 3.12 `--require-hashes` 安装与 `pip check` 通过。下一次远程尝试必须使用新的 commit 和 CI，不复用失败 run。
