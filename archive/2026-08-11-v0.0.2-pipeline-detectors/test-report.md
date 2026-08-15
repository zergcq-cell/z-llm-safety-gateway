# v0.2.0 Pipeline & Detectors — 测试报告

> 版本：v0.2.0
> 创建日期：2026-08-11
> 对应 Phase 2 Spec：design.md + 11 spec.yaml + test-plan.md

## 一、测试执行结果

### 1.1 总体结果

| 指标 | 数值 |
|------|------|
| **总测试数** | 544 |
| **通过** | 544 |
| **失败** | 0 |
| **跳过** | 0 |
| **通过率** | 100% |
| **代码覆盖率** | 95% |
| **执行时间** | ~3s |

### 1.2 测试分类统计

| 类别 | 测试文件数 | 测试用例数 | 状态 |
|------|-----------|-----------|------|
| config-system (v0.2.0) | 2 | 24 | 🟢 |
| detector-framework | 3 | 9 | 🟢 |
| circuit-breaker | 1 | 9 | 🟢 |
| pipeline-engine | 4 | 15 | 🟢 |
| language-detection | 1 | 7 | 🟢 |
| prompt-injection-detector | 1 | 22 | 🟢 |
| pii-detector | 1 | 13 | 🟢 |
| sensitive-words-detector | 1 | 16 | 🟢 |
| secret-leak-detector | 1 | 17 | 🟢 |
| toxicity-detector | 1 | 33 | 🟢 |
| fastapi-server (pipeline integration) | 4 | 23 | 🟢 |
| v0.1.0 回归测试 | 12 | 356 | 🟢 |
| **合计** | **32** | **544** | 🟢 |

### 1.3 代码覆盖率明细

| 模块 | 语句数 | 未覆盖 | 覆盖率 |
|------|--------|--------|--------|
| detectors/ (全部) | 428 | 24 | 94% |
| pipeline/ (全部) | 300 | 4 | 99% |
| circuit_breaker/ | 75 | 1 | 99% |
| language/ | 28 | 1 | 96% |
| config/ (全部) | 265 | 10 | 96% |
| middleware/ | 36 | 0 | 100% |
| routes/chat.py | 102 | 5 | 95% |
| exceptions.py | 23 | 0 | 100% |
| models.py | 30 | 0 | 100% |
| content/ | 58 | 4 | 93% |
| providers/ | 145 | 14 | 90% |
| app.py | 87 | 1 | 99% |
| **总计** | **1669** | **80** | **95%** |

## 二、TC 覆盖矩阵

### 2.1 P0 测试用例（全部通过）

| TC-ID | 模块 | 场景描述 | 状态 |
|-------|------|----------|------|
| TC-CONF-001~011 | config-system | 双向分组、扩展字段、阈值校验、旧格式兼容 | ✅ |
| TC-CONF-012~024 | config-system | 未知检测器、缺失文件、flag_escalation 语法 | ✅ |
| TC-DFRK-001~009 | detector-framework | Detector ABC、生命周期、注册表 | ✅ |
| TC-CB-001~009 | circuit-breaker | 三状态转换、阈值、超时、fallback | ✅ |
| TC-PIPE-001~015 | pipeline-engine | 并行执行、短路、错误处理、超时、聚合 | ✅ |
| TC-LANG-001~007 | language-detection | 语言检测、ISO 代码、空文本、异常 | ✅ |
| TC-INJ-001~005 | prompt-injection | 模式检测、DAN、阈值决策、initialize 编译 | ✅ |
| TC-PII-001~005 | pii-detector | email/phone 检测、mask/replace 脱敏、modify | ✅ |
| TC-SW-001~005 | sensitive-words | Aho-Corasick、中文词表、exact/fuzzy、阈值 | ✅ |
| TC-SEC-001~005 | secret-leak | API key/private key/JWT 检测、block | ✅ |
| TC-TOX-001~005 | toxicity-detector | 毒性检测、懒加载、首次加载、阈值 | ✅ |
| TC-FAST-001~005 | fastapi-server | input/output pipeline 集成、block/modify | ✅ |

### 2.2 P1 测试用例（全部通过）

| TC-ID 范围 | 模块 | 场景描述 | 状态 |
|-------------|------|----------|------|
| TC-INJ-006~011 | prompt-injection | 良性内容、confidence 计算、中文注入 | ✅ |
| TC-PII-006~011 | pii-detector | ssn/card/ip、hash、多 PII、entity_types | ✅ |
| TC-SW-006~013 | sensitive-words | 自动机、英文词表、文件加载、flag/allow | ✅ |
| TC-SEC-006~010 | secret-leak | 良性内容、可配置 patterns、自定义正则 | ✅ |
| TC-TOX-006~014 | toxicity-detector | offline、cache_dir、fail_open/closed | ✅ |
| TC-FAST-006~013 | fastapi-server | modify 写回、动态响应头、完整请求流 | ✅ |

### 2.3 P2 测试用例（全部通过）

| TC-ID 范围 | 模块 | 场景描述 | 状态 |
|-------------|------|----------|------|
| TC-INJ-012 | prompt-injection | 无效正则模式报错 | ✅ |
| TC-PII-012~013 | pii-detector | 默认 entity_types、无效正则 | ✅ |
| TC-SW-014~016 | sensitive-words | language=None 回退、仅英文、词表缺失 | ✅ |
| TC-SEC-011~013 | secret-leak | 默认 patterns、无效正则、覆盖默认 | ✅ |
| TC-TOX-015~016 | toxicity-detector | offline=false 下载、默认 version | ✅ |

## 三、质量检查

| 检查项 | 结果 |
|--------|------|
| `pytest tests/` 全量通过 | ✅ 544 passed |
| `ruff check src/ tests/` | ✅ All checks passed |
| `mypy src/` strict mode | ✅ Success: no issues found in 42 source files |
| 代码覆盖率 ≥ 80% | ✅ 95% |
| TC 覆盖率 100% | ✅ 161/161 TC 全部覆盖 |
| v0.1.0 回归无破坏 | ✅ 356 个回归测试全部通过 |

## 四、失败模式检查

### 4.1 已覆盖的失败模式

| 失败模式 | 覆盖测试 | 状态 |
|----------|----------|------|
| 检测器初始化失败（无效正则） | TC-INJ-012, TC-PII-013, TC-SEC-012 | ✅ |
| 词表文件缺失 | TC-SW-016 | ✅ |
| 模型加载失败（offline 模式） | TC-TOX-008 | ✅ |
| 模型加载失败（fail_open） | TC-TOX-012 | ✅ |
| 模型加载失败（fail_closed） | TC-TOX-013 | ✅ |
| 熔断器 OPEN 状态跳过 | TC-CB-006~009 | ✅ |
| 检测器超时 | TC-PIPE-014 | ✅ |
| 检测器异常 + fail_open | TC-PIPE-012 | ✅ |
| 检测器异常 + fail_closed | TC-PIPE-013 | ✅ |
| 输入 block → HTTP 400 | TC-FAST-003, TC-FAST-013 | ✅ |
| 输出 block → HTTP 422 | TC-FAST-004, TC-FAST-013 | ✅ |
| 无检测器 → 透传 | TC-FAST-010 | ✅ |
| 旧格式配置兼容 | TC-CONF-001, TC-CONF-012~014 | ✅ |

### 4.2 无新增失败模式

在 Phase 5 验证过程中未发现未覆盖的失败模式。

## 五、回归风险

| 风险区域 | v0.2.0 改动 | 回归保护 | 风险等级 |
|----------|-------------|----------|---------|
| config/models.py | DetectorsConfig 重构 | 24 个新测试 + 旧测试 | 🟢 |
| routes/chat.py | Pipeline 集成 | 23 个新测试 + 9 个旧集成测试 | 🟢 |
| middleware/safety_headers.py | 动态化 | 11 个新测试 + 3 个旧测试 | 🟢 |
| exceptions.py | SafetyBlockError | 2 个集成测试 | 🟢 |
| app.py | Pipeline 初始化 | 集成测试覆盖 | 🟢 |

## 六、结论

v0.2.0 Pipeline & Detectors 的全部 161 个测试用例已实现并通过验证。代码覆盖率达到 95%，超过 80% 的要求。ruff 和 mypy strict 检查全部通过。v0.1.0 的 356 个回归测试全部通过，无破坏性变更。
