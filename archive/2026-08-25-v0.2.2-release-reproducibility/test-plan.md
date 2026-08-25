# v0.2.2 测试方案与详细案例

> 版本：Gateway 0.2.2 / Detector SDK 0.1.1
> 创建日期：2026-08-25
> 对应 Phase 2 Spec：`release-hardening`、`github-setup`、`project-docs`

## 一、测试策略

### 1.1 测试金字塔

- **约 70% 静态与单元契约**：纯函数 mutation、YAML 结构、Action allowlist、lock/hash、
  evidence schema 和文档角色映射，无网络且确定性执行。
- **约 20% 构建与集成**：真实构建四个 distributions、Twine/metadata、依赖复用安装 smoke；
  GitHub runner 负责可信 clean-install。
- **约 10% 远程 E2E**：同 SHA main CI、manual dry-run、tag draft/public 状态、annotations、
  evidence artifact 和历史 refs，严格位于 Gate 3 后。

### 1.2 测试原则

- 严格 RED → GREEN → REFACTOR；每个 Scenario 先有可观察失败。
- 网络采集与纯判断分离，单元测试使用完整 JSON/refs fixture，不 mock 判断结果。
- 每个负向远程状态单独 mutation，只有明确 HTTP 404 可表示不存在。
- Action pin 必须同时满足官方仓库、精确 SHA 和 allowlist，不接受“任意 40 位 SHA”。
- 本地被 host packages 注入的 venv 只称 dependency-reuse smoke；clean 证据来自 GitHub runner。
- 公开 tag 永不重写；draft/public 失败保留证据并显式停止。
- evidence 字段使用白名单和 90 天保留期，不采集 secrets 或用户内容。

### 1.3 已有测试资产

| 测试文件 | 当前收集数 | 类型 | 覆盖范围 |
|----------|-----------:|------|----------|
| `tests/unit/release/test_release_contract.py` | 50 | 单元/构建 | 版本角色、notes、四产物、payload、workflow、安装 |
| `tests/unit/release/test_ci_contract.py` | 6 | 配置契约 | Python matrix、Ruff/Mypy/coverage、STDD quality |
| `tests/unit/release/test_documentation_contract.py` | 9 | 文档契约 | 当前版本、链接、配置、SDK/插件表面 |
| `tests/unit/stdd/test_agent_spec_checkpoints.py` | 8 | 元验证 | Agent spec node、collectability、远程命令与 shell 失败关闭 |
| 完整项目与两个示例插件 | 1066 | 全量回归 | Flow、HTTP/SSE、SDK、gRPC、YAML 与发布边界 |

## 二、详细测试案例

### 功能 1：可复现发布工具链

#### 案例 1.1 — 带哈希 lock 完整且精确

| 字段 | 内容 |
|------|------|
| **ID** | TC-REL-018 |
| **对应 Spec** | `release-hardening` → SC-REL-018 |
| **优先级** | P0 |
| **预置条件** | release-tools input、lock 和 workflow 可读取 |
| **输入** | 解析直接 pins、全部 requirements、hashes 和安装命令 |
| **预期结果** | 五个直接工具版本精确；每项 exact pin + SHA-256 hash；build/audit 使用同一 lock；无浮动工具安装；生成器固定 pip-tools 7.6.1 |
| **当前状态** | ✅ 本地通过 |

#### 案例 1.2 — 锁定 backend 的无隔离四产物构建

| 字段 | 内容 |
|------|------|
| **ID** | TC-REL-019 |
| **对应 Spec** | `release-hardening` → SC-REL-019 |
| **优先级** | P0 |
| **预置条件** | hash lock 已安装并包含 Hatchling |
| **输入** | 对根项目和 SDK 执行 `build --no-isolation`、Twine、metadata 与 CLI smoke |
| **预期结果** | 精确四产物；Gateway 0.2.2 / SDK 0.1.1；三个 CLI 在 clean runner 成功 |
| **当前状态** | ✅ 本地通过 |

### 功能 2：Draft-first 发布状态机

#### 案例 2.1 — Manual validation 与 tag publish 严格分离

| 字段 | 内容 |
|------|------|
| **ID** | TC-REL-020 |
| **对应 Spec** | `release-hardening` → SC-REL-020 |
| **优先级** | P0 |
| **预置条件** | Release workflow YAML |
| **输入** | 解析 triggers、needs、permissions 与 draft/publish 命令顺序 |
| **预期结果** | dispatch 无发布路径；tag-only release 依赖三门；只在 release job 写 contents；draft 先于 publish |
| **当前状态** | ✅ 本地契约通过；远程 pre-tag 待 Deliver |

#### 案例 2.2 — Draft payload、digest 和 peeled ref 精确通过

| 字段 | 内容 |
|------|------|
| **ID** | TC-REL-021 |
| **对应 Spec** | `release-hardening` → SC-REL-021 |
| **优先级** | P0 |
| **预置条件** | 合法 draft JSON、四个 uploaded assets/digests 和 annotated tag refs fixture |
| **输入** | 以 expected draft state 和 verified SHA 运行校验器 |
| **预期结果** | exact tag/body/assets/digests/state/peeled SHA 通过，targetCommitish 不参与身份判断 |
| **当前状态** | ✅ 本地通过 |

#### 案例 2.3 — 所有状态、资产和 ref mutation 失败闭合

| 字段 | 内容 |
|------|------|
| **ID** | TC-REL-022 |
| **对应 Spec** | `release-hardening` → SC-REL-022 |
| **优先级** | P0 |
| **预置条件** | 合法 fixture 及 existing/draft/public/digest/ref/error mutations |
| **输入** | 逐项运行状态机和纯校验函数 |
| **预期结果** | 每个 mutation 非零失败；不自动复用/覆盖 Release，不删除 tag，错误输出不泄密 |
| **当前状态** | ✅ 本地通过 |

### 功能 3：Evidence 与远程错误分类

#### 案例 3.1 — Evidence schema、排序、最小字段与保留期

| 字段 | 内容 |
|------|------|
| **ID** | TC-REL-023 |
| **对应 Spec** | `release-hardening` → SC-REL-023 |
| **优先级** | P0 |
| **预置条件** | 合法公开 Release JSON、refs、run/job metadata |
| **输入** | 两次以不同输入顺序生成 evidence，并解析 workflow artifact 配置 |
| **预期结果** | 输出字节稳定、assets 排序、字段白名单、无敏感字段、retention=90、Release assets 仍恰好四个 |
| **当前状态** | ✅ 本地通过 |

#### 案例 3.2 — Absence 只接受明确 404

| 字段 | 内容 |
|------|------|
| **ID** | TC-REL-024 |
| **对应 Spec** | `release-hardening` → SC-REL-024 |
| **优先级** | P0 |
| **预置条件** | 404、401、403、429、5xx、network、invalid JSON fixtures |
| **输入** | 运行结构化 absence parser |
| **预期结果** | 仅 404 返回 absent；其他情况稳定非零失败并阻止 draft |
| **当前状态** | ✅ 本地通过 |

#### 案例 3.3 — Gate 3 后远程交付闭环

| 字段 | 内容 |
|------|------|
| **ID** | TC-REL-025 |
| **对应 Spec** | `release-hardening` → SC-REL-025 |
| **优先级** | P1 |
| **预置条件** | Gate 3 批准、发布提交本地全绿、旧 refs/Release 基线已记录 |
| **输入** | push main → same-SHA CI → dispatch 0.2.2 → annotated tag → Release → evidence download |
| **预期结果** | 全链成功；dry-run 不发布；v0.2.2 peel=HEAD；evidence 合法；v0.2.0/v0.2.1 完全不变 |
| **当前状态** | ⏳ 3 个远程 checkpoint 待 Deliver；本地脚本/失败分支已验证 |

### 功能 4：Node 24 Action 与最小权限

#### 案例 4.1 — 官方 Node 24 Action 精确 SHA allowlist

| 字段 | 内容 |
|------|------|
| **ID** | TC-GH-008 |
| **对应 Spec** | `github-setup` → SC-GH-008 |
| **优先级** | P0 |
| **预置条件** | CI/Release workflows 与 design allowlist |
| **输入** | 枚举所有外部 `uses` 并解析 repo/ref/comment |
| **预期结果** | 四个官方 Actions 只使用核验 SHA，均为 node24 锚点并保留版本注释 |
| **当前状态** | ✅ 本地通过 |

#### 案例 4.2 — Dependabot 与锁更新契约

| 字段 | 内容 |
|------|------|
| **ID** | TC-GH-009 |
| **对应 Spec** | `github-setup` → SC-GH-009 |
| **优先级** | P0 |
| **预置条件** | Dependabot、release-tools input/lock 与维护说明 |
| **输入** | 解析三类更新范围和 lock regeneration 文档 |
| **预期结果** | root/SDK/Actions 覆盖不退化；Action SHA 与 lock hash 更新必须重新校验 |
| **当前状态** | ✅ 本地通过 |

#### 案例 4.3 — 三版本矩阵、完整 needs 和最小权限

| 字段 | 内容 |
|------|------|
| **ID** | TC-GH-010 |
| **对应 Spec** | `github-setup` → SC-GH-010 |
| **优先级** | P0 |
| **预置条件** | CI/Release workflows |
| **输入** | 解析 matrix、workflow_call、needs、if 与 permissions |
| **预期结果** | Python 3.10/3.11/3.12；release 复用 CI 并依赖三门；只有 tag release 可写 contents |
| **当前状态** | ✅ 本地通过 |

#### 案例 4.4 — 三类远程运行无 Node.js 20 annotation

| 字段 | 内容 |
|------|------|
| **ID** | TC-GH-011 |
| **对应 Spec** | `github-setup` → SC-GH-011 |
| **优先级** | P1 |
| **预置条件** | 同 SHA main、dispatch、tag 三类 GitHub runs |
| **输入** | 读取 mandatory jobs 与 check-run annotations |
| **预期结果** | 所有 jobs success；无 Node.js 20/node20 annotation；artifact digest mismatch 默认 error |
| **当前状态** | ⏳ 远程 annotations checkpoint 待 Deliver；本地失败分支已验证 |

### 功能 5：版本、路线图与历史文档

#### 案例 5.1 — Gateway/SDK 独立版本表面与兼容矩阵

| 字段 | 内容 |
|------|------|
| **ID** | TC-DOCS-011 |
| **对应 Spec** | `project-docs` → SC-DOCS-011 |
| **优先级** | P0 |
| **预置条件** | Gateway、SDK、双版本文档与配置表面 |
| **输入** | 按角色扫描版本和 wheel URL |
| **预期结果** | Gateway=0.2.2；SDK=0.1.1；兼容矩阵与 Python 支持正确；历史/SDK URL 不误改 |
| **当前状态** | ✅ 本地通过 |

#### 案例 5.2 — 路线图匹配真实发布历史

| 字段 | 内容 |
|------|------|
| **ID** | TC-DOCS-012 |
| **对应 Spec** | `project-docs` → SC-DOCS-012 |
| **优先级** | P1 |
| **预置条件** | DESIGN versioning/roadmap 与 README current version |
| **输入** | 扫描 v0.2.0/v0.2.1/v0.2.2/v0.3.0 表述与非目标声明 |
| **预期结果** | 已发布事实准确；不再 current v0.1.0；v0.3.0 独立确认；不虚构非目标已实现 |
| **当前状态** | ✅ 本地通过 |

#### 案例 5.3 — v0.2.2 notes 隔离且历史不可变

| 字段 | 内容 |
|------|------|
| **ID** | TC-DOCS-013 |
| **对应 Spec** | `project-docs` → SC-DOCS-013 |
| **优先级** | P0 |
| **预置条件** | CHANGELOG 相邻章节和 archive 历史 |
| **输入** | 提取 0.2.2 notes，并对历史章节/文件做负向 diff 契约 |
| **预期结果** | notes 仅含本维护范围和双版本；不混入相邻正文；历史不改写；明确运行时不变 |
| **当前状态** | ✅ 本地通过 |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 集成/构建 | 远程 E2E | 状态 |
|----------|----------|-----------|----------|------|
| release lock | pin/hash/command parser | no-isolation 四产物 | clean runner build | 🟡 本地通过 / 远程待验 |
| draft-first state | payload/ref mutations | workflow YAML sequence | pre-tag absence → draft → verify → publish | 🟡 本地通过 / 远程待验 |
| release evidence | schema/order/sanitization | artifact config | download + validate | 🟡 本地通过 / 远程待验 |
| Action pins | SHA allowlist | reusable workflow graph | annotations | 🟡 本地通过 / 远程待验 |
| 文档与版本 | role/history contracts | 四产物 metadata | Release notes/assets | 🟡 本地通过 / 远程待验 |
| 运行时兼容 | 完整 suite | Gateway/SDK install | 三 Python CI | 🟡 Python 3.10/3.12 本地通过；3.11 远程待验 |

## 四、回归风险矩阵

| 风险区域 | v0.2.2 改动 | 已有回归保护 | 风险等级 |
|----------|-------------|--------------|----------|
| GitHub Release 状态机 | public create 改为显式 draft/verify/publish | safe dry-run、needs、exact payload | 🔴 高 |
| Action runtime/pins | 四个 Action major 与 ref 变化 | CI matrix、Dependabot | 🔴 高 |
| 构建工具链 | hash lock、no-isolation Hatchling | 四产物/Twine/metadata | 🔴 高 |
| Evidence/远程分类 | 新 schema、digest、404 parser | v0.2.1 JSON validator | 🔴 高 |
| Gateway/SDK 版本 | Gateway 0.2.2，SDK 0.1.1 | 角色化版本与安装契约 | 🟡 中 |
| DESIGN/README | 纠正版本和路线图 | 文档链接/版本测试 | 🟡 中 |
| Flow/HTTP/SSE/gRPC/YAML | 无预期 diff | 1028 项完整回归 | 🟢 低 |

## 五、建议补充顺序

1. **P0（12）**：TC-REL-018～024、TC-GH-008～010、TC-DOCS-011、TC-DOCS-013。
2. **P1（3）**：TC-REL-025、TC-GH-011、TC-DOCS-012。
3. **P2（0）**：无；本 change 不保留低优先级行为缺口。

## 六、Gate 与停止条件

- Gate 2 前：15/15 Scenario 与 TC 映射、L3 锚定和文档审查必须通过。
- Gate 3 前：所有本地 TC node 必须 AST 存在且 collectable；完整 suite、Ruff、Mypy、coverage、
  四产物/Twine 通过；本机不可信 clean venv 仍须如实标记。
- Tag 前：同 SHA main CI 与 `workflow_dispatch(version=0.2.2)` 全绿，且 dispatch 未创建 Release。
- 发布后：v0.2.2 public payload/evidence 精确通过，v0.2.0/v0.2.1 基线不变。
- 任一远程状态不明确、Action annotation 回归、digest 缺失、已有 Release 或证据泄密时立即停止，
  不创建/移动 tag，不公开 draft。
