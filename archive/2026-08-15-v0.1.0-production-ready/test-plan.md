# v1.0.0 Production Ready 测试方案与详细案例

> 版本：v1.0.0
> 创建日期：2026-08-15
> 对应 Phase 2 Spec：accuracy-testing / project-docs / performance-benchmark / production-deployment / github-setup

## 一、测试策略

### 1.1 测试金字塔

本变更以 **文档/配置/测试基础设施** 为主（non-coding 为主），验证策略：
- **可执行资产**（accuracy 测试、benchmark 脚本）走单元/集成测试验证
- **文档/配置**（README、docs/、LICENSE、compose、CI）走 agent 检查点（file_exists / 内容断言 / 命令执行验证）
- **冒烟**：compose 单副本（可用时）、CI 本地等价命令

### 1.2 测试原则

- 文档中的每个命令与配置必须**逐条实测**（防文档漂移）
- accuracy 样本离线可复现，不依赖网络
- benchmark 结果为评审依据，不设 CI 硬门槛
- 不引入新第三方依赖

### 1.3 已有测试资产

| 测试文件 | 用例数 | 类型 | 覆盖范围 |
|----------|--------|------|----------|
| tests/unit/** | 700+ | 单元 | 配置/检测器/pipeline/插件/SDK |
| tests/integration/** | 90+ | 集成 | FastAPI/流式/审计/gRPC |
| 全量 | 796 | - | coverage 93% |

## 二、详细测试案例

### 功能 1：accuracy 测试（accuracy-testing）

#### 案例 1.1 — 样本集完整性与结构

| 字段 | 内容 |
|------|------|
| **ID** | TC-ACC-001 |
| **对应 Spec** | accuracy-testing → SC-ACC-001 |
| **优先级** | P0 |
| **预置条件** | tests/accuracy/samples/ 目录 |
| **输入** | 检查样本文件 |
| **预期结果** | 4 个规则型检测器各有样本 YAML；positive/negative ≥20 条；含预期 action 标注；无网络依赖 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.2 — 准确率阈值断言

| 字段 | 内容 |
|------|------|
| **ID** | TC-ACC-002 |
| **对应 Spec** | accuracy-testing → SC-ACC-002 |
| **优先级** | P0 |
| **预置条件** | 规则型检测器可初始化（无模型依赖） |
| **输入** | pytest tests/accuracy |
| **预期结果** | 各检测器准确率 ≥0.9；误报率 ≤0.1；toxicity 无模型时 skip |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.3 — 全量集成与失败可诊断

| 字段 | 内容 |
|------|------|
| **ID** | TC-ACC-003 |
| **对应 Spec** | accuracy-testing → SC-ACC-003 |
| **优先级** | P1 |
| **预置条件** | 全量测试套件 |
| **输入** | 全量 pytest |
| **预期结果** | accuracy 规则型用例 ≥4 个全绿；失败信息含具体判错样本 |
| **当前状态** | ❌ 测试缺 |

### 功能 2：project-docs

#### 案例 2.1 — LICENSE 合规

| 字段 | 内容 |
|------|------|
| **ID** | TC-DOCS-001 |
| **对应 Spec** | project-docs → SC-DOCS-001 |
| **优先级** | P0 |
| **预置条件** | 仓库根目录 |
| **输入** | 检查 LICENSE 文件 |
| **预期结果** | LICENSE 存在；含 "Apache License" + "Version 2.0"；9 个条款；与 pyproject 一致 |
| **当前状态** | ❌ 文件缺 |

#### 案例 2.2 — README 门面完整

| 字段 | 内容 |
|------|------|
| **ID** | TC-DOCS-002 |
| **对应 Spec** | project-docs → SC-DOCS-002 |
| **优先级** | P0 |
| **预置条件** | README.md |
| **输入** | 检查内容覆盖清单 |
| **预期结果** | 含介绍/特性/快速开始/配置示例/文档导航/许可；命令可执行 |
| **当前状态** | ❌ 待扩写 |

#### 案例 2.3 — 四份指南与实现一致

| 字段 | 内容 |
|------|------|
| **ID** | TC-DOCS-003 |
| **对应 Spec** | project-docs → SC-DOCS-003 |
| **优先级** | P0 |
| **预置条件** | docs/ 目录 |
| **输入** | 检查 4 份指南 + 逐条实测命令 |
| **预期结果** | 4 文件存在；覆盖要求章节；命令/配置实测通过 |
| **当前状态** | ❌ 文件缺 |

#### 案例 2.4 — DoD 清单可勾选

| 字段 | 内容 |
|------|------|
| **ID** | TC-DOCS-004 |
| **对应 Spec** | project-docs → SC-DOCS-004 |
| **优先级** | P2 |
| **预置条件** | proposal.md 与 test-report.md |
| **输入** | 检查 DoD 清单 |
| **预期结果** | 逐项可勾选是/否 |
| **当前状态** | ❌ 待写入 |

### 功能 3：performance-benchmark

#### 案例 3.1 — 基准脚本可运行

| 字段 | 内容 |
|------|------|
| **ID** | TC-BENCH-001 |
| **对应 Spec** | performance-benchmark → SC-BENCH-001 |
| **优先级** | P0 |
| **预置条件** | 规则型 pipeline 配置可用 |
| **输入** | python -m tests.benchmarks.bench_pipeline --suite latency |
| **预期结果** | exit 0；输出 P50/P95/P99；仅标准库 |
| **当前状态** | ❌ 脚本缺 |

#### 案例 3.2 — 目标对照报告

| 字段 | 内容 |
|------|------|
| **ID** | TC-BENCH-002 |
| **对应 Spec** | performance-benchmark → SC-BENCH-002 |
| **优先级** | P1 |
| **预置条件** | 基准运行完成 |
| **输入** | 检查报告输出 |
| **预期结果** | 对照表（目标/实测/达标）；未达标有说明；记录环境 |
| **当前状态** | ❌ 待实现 |

#### 案例 3.3 — 基准不阻塞 CI

| 字段 | 内容 |
|------|------|
| **ID** | TC-BENCH-003 |
| **对应 Spec** | performance-benchmark → SC-BENCH-003 |
| **优先级** | P2 |
| **预置条件** | CI workflow |
| **输入** | 检查 CI 内容 |
| **预期结果** | CI 不执行基准数值断言 |
| **当前状态** | ❌ 待验证 |

### 功能 4：production-deployment

#### 案例 4.1 — compose config 校验

| 字段 | 内容 |
|------|------|
| **ID** | TC-DEPL-001 |
| **对应 Spec** | production-deployment → SC-DEPL-001 |
| **优先级** | P0 |
| **预置条件** | docker-compose.prod.yml |
| **输入** | docker compose -f docker-compose.prod.yml config |
| **预期结果** | 校验通过；replicas≥2；resources.limits；healthcheck；restart |
| **当前状态** | ❌ 文件缺 |

#### 案例 4.2 — sidecar 集成

| 字段 | 内容 |
|------|------|
| **ID** | TC-DEPL-002 |
| **对应 Spec** | production-deployment → SC-DEPL-002 |
| **优先级** | P1 |
| **预置条件** | docker-compose.prod.yml |
| **输入** | 检查 sidecar 服务配置 |
| **预期结果** | 含 sidecar 服务 + 健康检查 + 资源限制 + 替换说明 |
| **当前状态** | ❌ 待实现 |

#### 案例 4.3 — 单副本冒烟（降级 config 校验）

| 字段 | 内容 |
|------|------|
| **ID** | TC-DEPL-003 |
| **对应 Spec** | production-deployment → SC-DEPL-003 |
| **优先级** | P2 |
| **预置条件** | 本地 Docker（或降级） |
| **输入** | docker compose up --scale gateway=1 |
| **预期结果** | 容器启动通过 healthcheck；无 Docker 时 config 校验通过 |
| **当前状态** | ❌ 待验证 |

### 功能 5：github-setup

#### 案例 5.1 — CI workflow 定义

| 字段 | 内容 |
|------|------|
| **ID** | TC-GH-001 |
| **对应 Spec** | github-setup → SC-GH-001 |
| **优先级** | P0 |
| **预置条件** | .github/workflows/ci.yml |
| **输入** | 检查 workflow 内容 |
| **预期结果** | push/PR 触发；3.10/3.11 矩阵；ruff+mypy+pytest；coverage gate ≥80%；含 sdk 路径 |
| **当前状态** | ❌ 文件缺 |

#### 案例 5.2 — 本地等价验证

| 字段 | 内容 |
|------|------|
| **ID** | TC-GH-002 |
| **对应 Spec** | github-setup → SC-GH-002 |
| **优先级** | P0 |
| **预置条件** | 本地仓库 |
| **输入** | 手动执行 CI 等价命令 |
| **预期结果** | ruff/mypy/pytest/coverage 全部成功 |
| **当前状态** | ✅ 部分（本地已全绿，需按 CI 命令复跑） |

#### 案例 5.3 — 贡献文件与模板

| 字段 | 内容 |
|------|------|
| **ID** | TC-GH-003 |
| **对应 Spec** | github-setup → SC-GH-003 |
| **优先级** | P1 |
| **预置条件** | 仓库根目录 + .github/ |
| **输入** | 检查文件存在性 |
| **预期结果** | CONTRIBUTING.md、ISSUE_TEMPLATE/、PULL_REQUEST_TEMPLATE.md 存在且内容合规 |
| **当前状态** | ❌ 文件缺 |

## 三、测试执行矩阵

| 功能模块 | 单元/脚本测试 | 集成 | 手动/检查点 | 状态 |
|----------|--------------|------|------------|------|
| accuracy 样本与断言 | ✅ pytest tests/accuracy | - | - | 🟡 待建 |
| LICENSE/README/docs | - | - | ✅ 检查点 + 命令实测 | 🟡 待建 |
| benchmark | ✅ 脚本运行 | - | ✅ 报告评审 | 🟡 待建 |
| compose prod | - | - | ✅ config 校验 + 冒烟 | 🟡 待建 |
| CI/CONTRIBUTING | - | - | ✅ 本地等价命令 | 🟡 待建 |

## 四、回归风险矩阵

| 风险区域 | v1.0.0 改动 | 已有回归保护 | 风险等级 |
|----------|-------------|-------------|---------|
| src/（运行时代码） | 无改动 | 796 用例全量回归 | 🟢 低 |
| sdk/ | 无改动 | 14 用例 | 🟢 低 |
| docs/ | 新增 4 份指南 | 命令实测 | 🟡 中（漂移风险） |
| tests/accuracy 样本 | 新增 | 离线固定样本 | 🟢 低 |
| CI 配置 | 新增 | 本地等价命令 | 🟡 中（环境差异） |
| compose prod | 新增 | config 校验 + 冒烟 | 🟡 中（无容器环境） |

## 五、建议补充顺序

1. **第一优先（P0）**：TC-ACC-001/002、TC-DOCS-001/002/003、TC-BENCH-001、TC-DEPL-001、TC-GH-001/002
2. **第二优先（P1）**：TC-ACC-003、TC-BENCH-002、TC-DEPL-002、TC-GH-003
3. **第三优先（P2）**：TC-DOCS-004、TC-BENCH-003、TC-DEPL-003
