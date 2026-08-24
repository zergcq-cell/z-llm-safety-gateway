# v0.2.1 独立版本发布热修复测试报告

> 测试日期：2026-08-24
> 测试环境：macOS / Python 3.10.20 / pytest 9.1.1
> 被测基线：`d67d573b0e38691707e70e64a7ec1a431ca1f545` + 当前未提交 hotfix diff

## 一、总体概况

| 指标 | 数值 |
|------|------|
| 测试用例总数 | 1028 |
| 通过 | 1027 |
| 失败 | 0 |
| 跳过 | 1（既有测试） |
| 通过率 | 100%（1027 / 1027，不计跳过） |
| 最终覆盖率运行耗时 | 23.95 秒 |
| Gateway 覆盖率 | 93.33%（门槛 90%） |

### 1.1 覆盖率诊断（变更代码）

| 变更文件 | 行覆盖率 | 状态 |
|----------|----------|------|
| `src/z_llm_safety_gateway/__init__.py` | 100% | ✅ |
| `tools/release_checks.py` | 84% | ⚠️ CLI 的 notes/输出分支未全部覆盖 |

`verify_version()`、`verify_release_payload()`、缺失/空 notes、Gateway/SDK mismatch、精确
Release body/assets/tag 及其 CLI 入口均有正负测试。工具文件未覆盖行主要是既有 notes stdout/
output 分支和防御性错误分支；核心新行为已覆盖，不阻塞本 hotfix。

## 二、按模块统计

| 测试模块 | 用例数 | 结果 | 说明 |
|----------|--------|------|------|
| 完整项目 + 两个示例插件 | 1028 | 1027 passed / 1 skipped | 包含 HTTP/SSE、Flow、SDK、gRPC、YAML 回归 |
| `tests/unit/release/` | 49 | 49 passed | checker、docs、workflow、build、Compose、SDK |
| Agent checkpoint 合同 | 2 | 2 passed | active/archive 定位与 23 个本地 targets |
| SDK package 合同 | 11 | 11 passed | SDK 0.1.1/API 独立性 |
| 四产物 + Twine | 4 artifacts | 全部通过 | 2 wheel + 2 sdist，版本/类型精确 |

## 三、E2E 与多版本结果

- 项目配置 `quality.e2e.enabled: false`，浏览器类 E2E 为 N/A；本 change 不含 UI。
- Python 3.10：本机完整质量门通过。
- Python 3.11 / 3.12：本机无对应隔离解释器，**SKIPPED**；Gate 3 后必须由同一 main SHA
  的 GitHub Actions 三版本矩阵补完，任一失败不得创建 tag。
- 本机“真正 clean venv”验证：**SKIPPED**。可用 Python 3.10 解释器会强制注入 TRAE
  tool-managed global site-packages，并把目标脚本装到全局工具目录，无法形成可信的 clean
  证据。现有本地测试只声明 dependency-reuse wheel smoke；Gate 3 后、tag 前必须运行
  `workflow_dispatch(version=0.2.1)`，由 GitHub runner 的 clean venv 完成普通依赖安装和三个
  CLI 检查。

## 四、失败与环境分析

最终自动化无失败。验证期间出现两类环境/预期失败：

1. 沙箱禁止绑定 `127.0.0.1:0`，13 个 gRPC setup 首轮报错；授权受控本机回环后同一套件
   1020/1026/1027 次序全部通过，结论为环境限制而非产品 bug。
2. 本机 bundled Python 的 child venv 仍注入全局包，不能作为 clean-install oracle；该检查
   如实标记 SKIPPED，并由 tag 前远程 dry-run 补完，不计作 PASS。

## 五、功能 / TC 覆盖对照

| Capability | TC | 自动化映射 | 当前执行 |
|------------|----|------------|----------|
| release-hardening | TC-REL-008～017（10） | 10/10 | 7 个本地 PASS；015～017 Deliver pending |
| detector-sdk | TC-SDK-010～012（3） | 3/3 | 3/3 PASS |
| project-docs | TC-DOCS-008～010（3） | 3/3 | 3/3 PASS |

TC 覆盖为 16/16；本地执行 13/13。三个远程 TC 不是豁免：它们依赖 Gate 3 后的 main push、
CI、workflow dry-run 与新 tag，已在 Canonical Agent specs 和 Deliver 任务中保留硬门。

### 5.1 切片完成度

| 切片 | TC 覆盖 | 新测试 | 验证结果 |
|------|---------|--------|----------|
| S1 版本角色校验 | 5/5 | 4 functions / 6 cases | ✅ 1017 passed 基线回归 |
| S2 双版本产物/CLI | 4/4 | 1 | ✅ 1018 passed；四产物正确 |
| S3 workflow/公开表面 | 5/5 | 1 | ✅ 1019 passed；版本角色一致 |
| S4 checkpoint/thorough 前置 | 16/16 mapped | 1 | ✅ 23 targets；最终 1027 passed |

## 五-B、多路并行 Review 结果

### Review 迭代历史

| 轮次 | 代码质量 | 测试/配置 | 文档/Skills | 结论 |
|------|----------|-----------|-------------|------|
| 1 | C0 H2 M1 L0 | C0 H3 M2 L0 | C0 H2 M4 L2 | 修复真实 H/M 缺口 |
| 2 | C0 H0 M1 L0 | C0 H0 M0 L0 | C0 H1 M1 L1 | 增强远程精确证据 |
| 3 | C0 H0 M0 L0 | C0 H0 M0 L0 | C0 H0 M0 L0 | ✅ 通过 |

### 已修复问题

- Production Compose image 与契约从 0.2.0 修正为 0.2.1。
- hotfix checkpoint 定位同时支持 `changes/` 与 `archive/`。
- workflow tag/manual 版本来源与四产物 `(name, version, kind)` 改为精确断言。
- SDK README、CLI template、插件和示例 wheel 引用全部纳入 0.1.1 契约。
- CP-REL-016 使用 deterministic JSON validator 精确比较 tag、notes 与四 assets，并核对
  peeled tag == verified HEAD。
- CP-REL-017 只接受明确 HTTP 404，认证/网络/服务失败不再被当成“Release 不存在”。

最终没有未修复的 C/H/M/L review finding。

## 六、设计调整说明

无设计调整；Review 修复均补全锁定 Scenario。详见
[design-adjustments.md](design-adjustments.md)。

## 七、十二类失败模式检查

| 类别 | 实际检查与证据 | 结果 |
|------|----------------|------|
| (a) 幻觉行为 | Canonical 2/2、23 checkpoint AST/collect、路径与 CLI 实查 | ✅ |
| (b) 范围蔓延 | 22 个 tracked diff 文件均属于 checker/version/workflow/docs/tests | ✅ |
| (c) 级联错误 | 远程 absence 仅接受 HTTP 404；其他错误显式失败 | ✅ |
| (d) 上下文丢失 | Gateway 0.2.1 / SDK 0.1.1 与 Phase 2 决策一致 | ✅ |
| (e) 工具误用 | bundled venv 假隔离已识别并标记 SKIPPED；远程补门明确 | ✅ 已处置 |
| (f) 运行时行为偏差 | checker 函数、CLI、真实构建与三个 entry-point smoke | ✅ |
| (g) 管线断链 | verify → build 4 artifacts → Twine → release JSON validator | ✅ |
| (h) 内容质量偏差 | 公开版本、链接、CHANGELOG 精确分节与失败事实契约 | ✅ |
| (i) 指令衰减 | 三 Gate 保留；Phase 3–5 未 commit/tag/push；v0.2.0 未改写 | ✅ |
| (j) 覆盖真空 | 3 capabilities 均有自动化；TC 16/16 映射 | ✅ |
| (k) 契约断层 | Gateway/tag 与 SDK 内部版本按角色精确校验 | ✅ |
| (l) 锚定缺失 | 两个参考 change 存在；远程 tag object/peeled SHA 与基线一致 | ✅ |

远程只读证据：`v0.2.0` tag object `dae034025cc7f68d13ef7b9b3ba3f1b1eca35411`，
peeled commit `d67d573b0e38691707e70e64a7ec1a431ca1f545`，GitHub Release API 明确
`HTTP/2.0 404 Not Found`。

## 七-B、经验库更新

| 类型 | ID | 内容 |
|------|----|------|
| 新增 | EXP-2026-0014 | bundled Python 全局包注入使 child venv clean 证据失真 |
| 新增 | EXP-2026-0015 | 远程不存在检查必须区分明确 404 与其他失败 |
| 新增 | EXP-2026-0016 | Release 存在不等于 notes/assets/tag commit 精确正确 |
| 复用 | EXP-2026-0004 | tag 发布依赖完整质量矩阵 |
| 复用 | EXP-2026-0005 | 公开配置/文档表面需要契约测试 |
| 复用 | EXP-2026-0006 | Agent checkpoint 必须真实且 archive-stable |

本次新增 3、复用 3，经验库总计 16 条。

## 七-C、项目原则复核

| 原则 | 实际结果与证据 | 状态 |
|------|---------------|------|
| Plugin / Flow；核心最小 | 仅发布工具/元数据/文档/测试变化；Flow 与插件运行时 diff 为零 | ✅ |
| 策略显式；失败不静默 | Gateway mismatch、SDK mismatch、notes/assets/tag/404 全部硬失败 | ✅ |
| 边界透明；契约稳定 | Gateway 补丁升级；HTTP/SSE/YAML/SDK API 不变；SDK 仍 0.1.1 | ✅ |
| 决策有证据；数据保护 | tag/commit/jobs/notes/assets 构成证据；仅处理公开元数据 | ✅ |

原则取舍仍为：保留失败 v0.2.0 公开 tag 的不可变性，以新 v0.2.1 修复发布。无原则偏离。

## 八、结论与未完成项

本地代码与产物质量门全部通过，可以进入 Gate 3。以下项目尚未完成，必须逐项保留：

1. **Python 3.11/3.12 同 SHA CI** — 原因：本机仅有可信 Python 3.10；影响：跨版本回归尚无
   本次提交远程证据；计划：Gate 3 后 push main，等待 3.10/3.11/3.12 全绿，失败则停止。
2. **真正 clean install** — 原因：本机 bundled 解释器污染 child venv；影响：本地 smoke
   不能证明依赖解析隔离；计划：main CI 后先运行 `workflow_dispatch(version=0.2.1)` 并等待
   quality/build/audit 全绿，失败则不创建 tag。
3. **TC-REL-015** — 原因：需要 Gate 3 后 push main；影响：tag 前远程质量链未完成；计划同 1。
4. **TC-REL-016** — 原因：v0.2.1 tag/Release 尚不存在；影响：远程四 assets/notes/tag SHA
   尚未验证；计划：仅在 1–3 全绿后创建新 tag，再用 deterministic validator 验证。
5. **TC-REL-017 发布后复核** — 原因：需比较 v0.2.1 发布前后状态；影响：当前只有发布前
   基线；计划：发布后再次读取 v0.2.0 refs 与 Release 404，必须完全不变。

### 8.1 质量信号汇总

| 信号源 | 状态 | 备注 |
|--------|------|------|
| 单元/集成测试 | ✅ | 1027 passed / 1 skipped，100% |
| Ruff | ✅ | 全范围通过 |
| Mypy | ✅ | 99 source files 通过 |
| 覆盖率 | ✅ | 93.33% ≥ 90% |
| 构建/Twine | ✅ | 四产物全部通过 |
| 多 Python | ⚠️ pending | 3.10 本地通过；3.11/3.12 待 main CI |
| Clean install | ⚠️ pending | 本地 SKIPPED；待 workflow_dispatch |
| Review | ✅ | 三轮最终 C0 H0 M0 L0 |
| 十二类失败模式 | ✅ | 12/12 已检查，无未修复命中 |
| 设计调整 | ✅ | 0；无需 re-spec/re-build |
