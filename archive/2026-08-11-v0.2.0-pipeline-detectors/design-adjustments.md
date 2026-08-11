# v0.2.0 Pipeline & Detectors — 设计偏差记录

> 创建日期：2026-08-11
> 对应 design.md：v0.2.0 技术设计

## 偏差总览

| # | 偏差描述 | 影响等级 | 状态 |
|---|----------|---------|------|
| 1 | PII 检测器注册名使用 `pii_redaction` 而非 `pii` | 低 | 已记录 |
| 2 | 检测器初始化使用 asyncio.run() 而非 startup event | 低 | 已记录 |
| 3 | 敏感词检测器 confidence 使用离散值 (0.0/0.5/1.0) 而非线性映射 | 低 | 已记录 |
| 4 | 毒性检测器 on_error 处理在检测器内部完成而非依赖管道引擎 | 中 | 已记录 |

## 详细偏差

### 1. PII 检测器注册名

**设计描述**：design.md Decision 3 提到内置检测器通过 name → class 映射注册。config 验证器中已知检测器列表使用 `pii_redaction` 作为 PII 检测器的名称。

**实际实现**：在 `create_default_registry()` 中，PII 检测器注册为 `pii_redaction`（与 config 验证器的已知检测器列表一致），而非 `pii`。

**原因**：config 验证器（`validators.py`）在 v0.2.0 重构时已使用 `pii_redaction` 作为 PII 检测器的配置名称。为保持一致性，注册名也使用 `pii_redaction`。

**影响**：配置文件中 PII 检测器的 `name` 字段必须使用 `pii_redaction`。

### 2. 检测器初始化方式

**设计描述**：design.md Decision 11 提到 app.py 中初始化 DetectorRegistry + PipelineEngine。

**实际实现**：在同步的 `create_app()` 函数中使用 `asyncio.run()` 急切初始化检测器，而非使用 FastAPI 的 `@app.on_event("startup")` 异步事件。

**原因**：`create_app()` 是同步函数，TestClient 创建时不会自动触发 startup 事件（需要 `with TestClient(app) as client:` 上下文管理器）。使用 `asyncio.run()` 确保检测器在应用创建时就完成初始化，简化测试代码。

**影响**：检测器初始化在 `create_app()` 调用时同步完成，而非在服务器启动时。对于重量级检测器（如 ToxicityDetector），由于采用懒加载设计，initialize() 只存储配置不加载模型，因此不会阻塞。

### 3. 敏感词检测器 confidence 计算

**设计描述**：DESIGN.md Section 5.3 要求检测器只计算 confidence，管道引擎通过 ThresholdDecisionEngine 决定 action。

**实际实现**：敏感词检测器使用离散 confidence 值（0.0/0.5/1.0）而非线性映射。具体逻辑：
- 0 匹配 → confidence=0.0
- flag_threshold ≤ 匹配数 < block_threshold → confidence=0.5
- 匹配数 ≥ block_threshold → confidence=1.0

检测器同时直接设置 action（block/flag/allow），因为管道引擎的 ThresholdDecisionEngine 使用浮点阈值（从 config 读取的 block_threshold/flag_threshold 可能是整数计数值），直接使用会导致决策错误。

**原因**：敏感词检测器的阈值是计数型（如 block_threshold=3 表示匹配 3 个词时 block），而 DetectionResult.confidence 限制在 [0.0, 1.0]。如果将计数阈值直接传给 ThresholdDecisionEngine，confidence 永远无法达到阈值（如 3.0）。

**影响**：敏感词检测器的 action 由检测器自身决定，而非管道引擎。但其他检测器（prompt_injection, toxicity）仍由管道引擎决定 action。

### 4. 毒性检测器 on_error 处理位置

**设计描述**：design.md Decision 9 提到模型加载失败时按 on_error 策略处理。

**实际实现**：ToxicityDetector 在 `detect()` 方法内部处理模型加载失败，直接返回带有 action='allow'（fail_open）或 action='block'（fail_closed）的 DetectionResult，而非抛出异常让管道引擎处理。

**原因**：管道引擎的 on_error 处理针对的是检测器 `detect()` 方法抛出异常的情况。但模型加载失败是一个可预期的失败模式，检测器可以自行处理并返回适当的结果，避免异常传播的开销。管道引擎仍会处理 detect() 抛出的其他未预期异常。

**影响**：毒性检测器的 on_error 策略在检测器内部生效。管道引擎的 on_error 配置仍作为兜底处理其他异常。

## 无偏差项

以下设计决策完全按 design.md 实现，无偏差：

- Decision 1: asyncio.Task 并行 + 短路取消 ✅
- Decision 2: DetectionResult/DetectionContext 定义位置 ✅
- Decision 4: 熔断器状态机 ✅
- Decision 5: 阈值驱动决策引擎（prompt_injection, toxicity） ✅
- Decision 6: 结果聚合策略 ✅
- Decision 7: Flag 升级规则 DSL ✅
- Decision 8: Aho-Corasick 自动机 ✅
- Decision 10: 配置系统重构 ✅
- Decision 11: 请求流集成 ✅
- Decision 12: Block 错误响应格式 ✅
