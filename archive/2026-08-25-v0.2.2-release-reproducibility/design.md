# v0.2.2 发布可复现性与证据闭环 - 技术设计

## Context

Gateway `v0.2.1` 与独立 Detector SDK `v0.1.1` 已由提交
`c8daffcef87326c377aa4abd945a46a6455da1eb` 成功发布。现有 Release workflow 已具备
Python 3.10/3.11/3.12 quality、四产物 build、clean-install、生产依赖 audit 和 tag-only
发布门，但仍存在以下缺口：

1. `actions/checkout@v4`、`actions/setup-python@v5` 和 artifact v4 在 GitHub runner 上产生
   Node.js 20 弃用告警，后续可能由警告升级为运行失败。
2. `pip`、`build`、`twine`、`pip-audit` 以及隔离构建中的 Hatchling 在运行时动态解析，
   同一提交的发布工具环境不能由仓库内容完整复现。
3. 当前 `gh release create` 在创建公开 Release 后才由维护者运行确定性 JSON 校验；公开前
   没有仓库内的 exact payload、digest、tag commit 闭环。
4. Gate 3 测试报告是发布前快照，远程 CI、dry-run、Release 和 assets 证据没有统一的机器
   可读输出；`DESIGN.md` 中的当前版本与 v0.2.x 路线图也已落后于事实。

本 change 只修改发布工具、GitHub workflows、发布版本表面、契约测试和文档。Gateway
更新到 `0.2.2`，Detector SDK 保持 `0.1.1`。Flow、Pipeline、HTTP/SSE、Provider、gRPC、
Detector SDK API 和 YAML 运行时行为保持不变。

### 已核验的官方 Action 锚点

2026-08-25 通过 GitHub API 读取官方 release、tag ref 和 `action.yml`，以下 tag 均直接指向
commit 且声明 `runs.using: node24`：

| Action | 官方版本 | 固定 commit SHA |
|--------|----------|-----------------|
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-python` | `v7.0.0` | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| `actions/upload-artifact` | `v7.0.1` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `actions/download-artifact` | `v8.0.1` | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` |

`download-artifact@v8` 默认将 digest mismatch 视为 error，符合失败显式原则。所有 workflow
引用使用完整 SHA，并在同行注释语义版本，Dependabot 继续负责 GitHub Actions 更新提案。

### 已核验的发布工具锚点

2026-08-25 通过 PyPI JSON 核验以下稳定版本均未 yanked：`pip==26.2.1`、`build==1.5.0`、
`twine==7.0.0`、`pip-audit==2.10.1`、`hatchling==1.32.0`。Phase 4 将用受审查的锁定生成流程
解析完整传递依赖和 hashes，而不是手工猜测锁文件内容；生成器固定为未 yanked 的
`pip-tools==7.6.1`，但生成器本身不安装到发布运行环境。

## Project Principle Check

| 原则 | 本设计如何满足 | 风险或取舍 | 验证方式 |
|------|---------------|-----------|---------|
| Plugin / Flow；核心最小 | 发布状态机和校验器保留在 `.github/`、`tools/` 与测试中，不进入 Gateway runtime；不新增领域能力 | 本 change 不扩展 Flow 或插件能力 | diff contract 禁止修改 Flow、pipeline、provider、proto 与 SDK API 行为 |
| 策略显式；失败不静默 | draft/public 状态、已有 Release、digest 缺失、404/认证/网络错误、证据上传失败均有稳定失败路径 | 校验失败可能留下私有 draft；选择保留证据而非自动删除 | 状态机负向测试、workflow needs/if 契约和远程 dry-run/tag 验收 |
| 边界透明；契约稳定 | 继续交付四个公开 distributions；Gateway 0.2.2 与 SDK 0.1.1 独立；所有运行时协议不变 | 新增 Actions artifact，但不改变 GitHub Release asset 集合 | metadata 集合、公开 assets multiset、版本表面与全量回归测试 |
| 决策有证据；数据默认保护 | 输出有 schema、排序稳定、仅含公开 commit/run/release/asset metadata 的 evidence；保留期固定为 90 天 | Actions artifact 不是永久账本；Release 与 tag 本身仍是长期锚点 | evidence schema、禁止字段、retention-days、notes hash 与远程 refs 校验 |

**原则取舍**：draft 校验失败时保留非公开草稿会增加一次显式人工处置，但可防止自动清理
掩盖失败或误删诊断材料。删除失败 draft 需要维护者单独确认；任何公开 tag 均不重写。

## Decisions

### 1. 官方 Actions 使用 Node 24 版本并固定完整 SHA

**方案**：CI 与 Release workflows 使用上表四个精确 commit SHA，同行保留 `# vX.Y.Z` 注释。
契约测试解析所有 `uses: owner/repo@ref`，要求官方 Action ref 为 40 位小写 SHA，并精确落在
本 change 核验的 allowlist。远程验收检查 CI、dry-run 和 tag run 没有 Node.js 20 annotation。

**为什么**：major tag 可移动，完整 SHA 才能形成稳定供应链锚点；Node 24 消除已观察到的
Node.js 20 弃用风险。

**备选方案及排除原因**：

- 只从 v4/v5 升级到浮动 `@v7`：消除告警但不能防止 tag 移动或无审查更新。
- 继续使用旧版本等待 GitHub 强制迁移：会把确定的弃用风险带入下一次发布。
- 接受任意 40 位 SHA：不能证明 SHA 属于官方已核验版本，因此使用精确 allowlist。

### 2. 使用带哈希的 release-tools lock 与无隔离构建

**方案**：新增 `requirements/release-tools.in`，固定五个直接工具版本；生成
`requirements/release-tools.lock`，完整固定传递依赖与 SHA-256 hashes。build 与 audit job
均使用 `python -m pip install --require-hashes -r requirements/release-tools.lock`。构建根项目
与 SDK 时使用 `python -m build --no-isolation`，确保实际 backend 是锁定的 Hatchling。

锁文件生成命令固定记录为 Python 3.12 clean venv 中安装 `pip-tools==7.6.1` 后执行
`pip-compile --generate-hashes --resolver=backtracking --output-file requirements/release-tools.lock requirements/release-tools.in`。

锁文件更新必须由显式脚本或记录的命令生成，契约测试检查：五个直接 pin 精确、lock 无
范围版本、每个 requirement 有 hash、workflow 没有 `pip install --upgrade ... build/twine`，
并且两个 build 命令都有 `--no-isolation`。

**为什么**：只固定 `build` 命令但允许隔离环境动态安装 Hatchling，仍会形成构建后端漂移；
带 hash 的完整锁文件同时约束版本和下载内容。

**备选方案及排除原因**：

- 只固定顶层五个版本：传递依赖仍会随时间变化。
- 保留 `python -m build` 隔离模式：隔离环境不会自动继承 release lock 中的 Hatchling。
- 在 `pyproject.toml` 将所有开发依赖改为 exact pin：会不必要地约束普通开发环境；发布锁应独立。

### 3. 使用显式 draft-first 状态机

**方案**：release job 保持 tag-only 且依赖 `quality`、`build`、`audit`，执行以下状态机：

1. 对目标 tag 查询 Release API；仅明确 404 允许继续。
2. 使用 `gh release create --draft --verify-tag` 创建私有 draft 并上传四个 distributions。
3. 读取 draft JSON 与远程 tag object/peeled commit，执行确定性校验。
4. 全部通过后执行 `gh release edit <tag> --draft=false`。
5. 再读取公开 JSON，验证 `isDraft=false`、`isPrerelease=false` 和相同 payload。

已有 draft、已有 published Release、非 404 API 失败、部分 assets、digest 缺失或 tag 错配全部
硬失败。失败 draft 不自动删除；诊断指引要求维护者检查后明确删除 draft，再 rerun 同一失败
workflow。tag 永不自动删除或移动。

**为什么**：公开状态是不可逆或高成本动作，应当位于完整验证之后；保留失败草稿比自动清理
更可审计。

**备选方案及排除原因**：

- 保持公开创建后人工校验：存在未验证内容已公开的窗口。
- 校验失败时自动删除 draft：可能掩盖错误，且扩大 workflow 的破坏权限。
- 自动复用已有 draft：可能混入上一次运行的部分资产或 notes，导致状态不确定。

### 4. 扩展纯确定性 Release payload 与 ref 校验

**方案**：保持 JSON-first 的纯函数边界，扩展 `tools/release_checks.py`：

- Draft 创建前从本地 `dist/` 四产物生成按文件名绑定的 SHA-256 清单。
- Release payload：精确 tag、CHANGELOG body、四资产 multiset、每个 asset `state=uploaded`、
  远程 `digest` 与同名本地产物 SHA-256 完全相等、期望的 `isDraft`、`isPrerelease=false`。
- Remote refs：tag object 非空、peeled commit 精确等于 `GITHUB_SHA`，输入缺失或多值失败。
- Absence：只接受结构化的明确 HTTP 404；401/403/429/5xx、网络和 JSON 错误全部失败。
- CLI 显式接收期望状态和 refs 文件/参数，不在纯校验函数内部发网络请求。

资产顺序在比较与 evidence 输出前排序；重复名称、同长度错误 digest 或资产间 digest 互换
全部失败。错误只包含稳定字段和值，不输出 token、完整环境或响应 headers。

**为什么**：网络采集与确定性判断分离，使负向测试不依赖 GitHub，同时避免任意命令失败被
误判成资源不存在。

**备选方案及排除原因**：

- 在 Python 校验器内直接调用 GitHub API：单元测试需要网络且混合认证、重试和业务判断。
- 只比较资产名称：不能证明上传完成或 GitHub 记录了内容 digest。
- 使用 `targetCommitish` 证明 tag commit：annotated tag 场景下该字段可能显示默认分支，必须使用 peeled ref。

### 5. Evidence 是有界 Actions artifact，不是第五个 Release asset

**方案**：公开校验通过后生成 schema version 1 的 `release-evidence.json`，字段固定为：

- Gateway/SDK version；tag、tag object、peeled commit；
- workflow repository、run ID、run attempt、run URL；
- required job conclusions；Release URL、状态、notes SHA-256；
- 按名称排序的四个 asset name/size/digest；验证时间与 verifier schema version。

禁止包含环境变量全集、headers、actor email、token、原始 API 错误正文或用户内容。使用固定
artifact 名 `release-evidence-v0.2.2`、`retention-days: 90`、`if-no-files-found: error`，并把
同一非敏感摘要写入 `$GITHUB_STEP_SUMMARY`。Evidence 上传失败使 workflow 失败，但不触发
自动回滚已验证的公开 tag/Release。

**为什么**：保留四个公开 distribution 的稳定资产契约，同时让远程 Deliver 证据可下载、
可机器消费且有明确保留期限。

**备选方案及排除原因**：

- 把 evidence 加为第五个 Release asset：破坏既有 exact-four 公开契约。
- 将远程结果自动 commit 回 main：会使 tag SHA 与 main 交付 SHA 分叉，并需要写仓库权限。
- 永久保存完整 API payload：包含多余动态元数据，违反数据最小化。

### 6. 事件和权限边界保持最小且显式

**方案**：`workflow_dispatch(version=0.2.2)` 只执行 quality/build/audit 和四产物/clean-install
验证，release job 继续由 `push` + `refs/tags/v*` 条件保护。workflow 顶层 `contents: read`；
只有 release job 使用 `contents: write`，不增加 `actions: write`、`id-token: write` 或其他权限。
Evidence 使用当前 workflow artifact，无需新 token 或外部服务。

**为什么**：发布能力只在最小 job 和最小事件边界可用，dry-run 不具备对外写入路径。

**备选方案及排除原因**：

- workflow 顶层授予 `contents: write`：让 quality/build/audit 获得不必要权限。
- 增加 workflow_run 自动链：扩大跨 workflow 状态与权限复杂度。
- 在本 change 引入 attestation 权限：SBOM/SLSA 已明确为非目标。

### 7. 版本与路线图按角色和事实更新

**方案**：Gateway metadata/runtime、README、Gateway 文档、config comments 和 production
Compose 更新到 `0.2.2`；SDK metadata/runtime、SDK README wheel、CLI template 和示例依赖
保持 `0.1.1`。CHANGELOG 新增 v0.2.2 章节但不改写 0.2.0/0.2.1 历史。

`DESIGN.md` 修正过期的“current v0.1.0”，区分 v0.2.0 tag 已发布但 Release workflow
失败、v0.2.1 Release 成功和当前 v0.2.2 源码 / release candidate；只有 Deliver 成功后才把
v0.2.2 标为已发布 Release。v0.3.0 保持下一功能里程碑，具体范围仍由独立 STDD change
确认。README 或相关文档增加 Gateway/SDK 独立版本兼容矩阵。

**为什么**：角色化版本映射延续 v0.2.1 的独立包契约；只纠正已知事实可避免路线图范围蔓延。

**备选方案及排除原因**：

- 同步将 SDK 升到 0.2.2：SDK 无 API/实现变化，会制造虚假版本语义。
- 全仓字符串替换：会改写历史 CHANGELOG、archive 和 SDK 下载链接。
- 在本 change 重新定义 v0.3.0 产品范围：超出发布维护补丁边界。

### 8. 本地纯测试、真实构建与远程验收分层

**方案**：严格 RED → GREEN → REFACTOR：

- 单元/契约层：lock、Action allowlist、workflow 状态机、payload mutations、evidence schema、文档映射。
- 构建层：Gateway 0.2.2 / SDK 0.1.1 四产物、Twine、依赖复用 smoke；真正 clean install 由 GitHub runner 执行。
- 回归层：完整 pytest + coverage、Ruff、Mypy，覆盖 Flow/HTTP/SSE/SDK/gRPC/YAML。
- 远程层：同 SHA main CI、workflow_dispatch dry-run 后立即执行 pre-tag absence checkpoint，
  再执行 tag release、annotations、evidence artifact 与旧 tag refs 复核。pre-tag checkpoint
  必须同时观察 v0.2.2 Release 明确 404 和远程 tag 不存在，不能用发布后的最终状态倒推。

Agent checkpoints 使用计划中的精确 pytest nodes；Build 完成前必须以 AST 和
`pytest --collect-only` 证明所有本地 node 真实存在，并保证 change 归档后仍可定位。

**为什么**：复用 EXP-0004/0006/0014/0015/0016，避免假隔离、假 checkpoint、远程错误
误分类和只验证 Release 存在的假绿。

**备选方案及排除原因**：

- 在被注入全局包的本机 venv 声明 clean PASS：证据不可信。
- 只做静态 workflow YAML 检查：不能证明 GitHub event、权限和 draft/public 状态。
- 发布后修改 tag 内归档报告：会改变已验证提交；远程结果应由 evidence artifact 承载。

## Architecture

```text
                         ┌─────────────────────────────┐
main / PR / workflow_call│ quality: Python 3.10-3.12 │
                         └──────────────┬──────────────┘
                                        │
tag push / workflow_dispatch            │
        │                               │
        ├─ version verify               │
        ├─ hashed tool lock install     │
        ├─ build --no-isolation         │
        ├─ four artifacts + Twine       │
        ├─ clean-install / 3 CLIs       │
        └─ audit resolved runtime deps  │
                 │                      │
                 └──── all success ─────┘
                            │
                  workflow_dispatch? ── yes ──► stop: validation only
                            │ no (tag push)
                            ▼
                  explicit Release absence (404)
                            │
                  create private draft + 4 assets
                            │
          release JSON + tag refs ──► deterministic validator
                            │ exact draft payload + digests + peeled SHA
                            ▼
                     publish draft
                            │
                  exact public-state recheck
                            │
          release-evidence.json + Job Summary (90 days)
```

失败路径：

```text
quality/build/audit failure  → no draft, no public Release
absence check non-404        → no draft, explicit failure
draft validation failure     → private draft retained, public Release absent
publish/public recheck fail  → workflow red, tag/Release never auto-deleted
evidence upload failure      → workflow red, verified public state retained
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 官方 Action 新 major 有 ESM、artifact digest 等行为变化 | 固定已核验 SHA；执行三事件远程回归；download digest mismatch 保持默认 error |
| 完整 hash lock 在依赖更新时维护成本增加 | 记录确定性生成命令；Dependabot 提案后重新生成并审查 diff |
| `build --no-isolation` 缺少 backend 时失败 | lock 显式包含 Hatchling；契约测试检查 backend pin 和命令 |
| draft 验证失败留下私有状态 | 明确诊断和人工删除步骤；不自动删除或复用 draft |
| GitHub assets digest 字段暂时缺失 | fail closed；不得降级为仅名称验证 |
| 公开后 evidence 上传失败 | workflow 显式失败；不重写 tag/Release，可手工下载公开元数据重建证据 |
| 90 天 artifact 不是永久存档 | 长期事实仍由 immutable tag、Release、assets digests 和 Actions run 保留 |
| 文档版本更新误改 SDK 或历史 | 角色化表面清单与负向字符串契约，archive/历史 CHANGELOG 排除 |
