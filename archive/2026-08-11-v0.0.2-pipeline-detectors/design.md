# v0.2.0 - Pipeline & Detectors - 技术设计

## Context

v0.1.0 已实现框架骨架：FastAPI 应用工厂、YAML 配置加载、Provider 代理（OpenAI/Azure/兼容）、内容提取器（ExtractedContent + Modification）、请求 ID 中间件、健康检查端点。但请求流是纯透传，无安全检测能力。

技术栈：Python 3.10+ / FastAPI / Pydantic v2 / httpx / structlog / pytest + pytest-asyncio / ruff / mypy (strict)

现有代码基础：
- `src/z_llm_safety_gateway/models.py` — ExtractedContent + Modification
- `src/z_llm_safety_gateway/content/extractor.py` — extract_content()
- `src/z_llm_safety_gateway/content/writeback.py` — apply_modifications()
- `src/z_llm_safety_gateway/config/models.py` — PipelineConfig (detectors: list[dict]), DetectorConfig
- `src/z_llm_safety_gateway/routes/chat.py` — 纯透传 /v1/chat/completions
- `src/z_llm_safety_gateway/middleware/safety_headers.py` — 硬编码 X-Safety-Action: allow

DESIGN.md 参考：Section 5 (Pipeline Engine), Section 6 (Detector System), Section 10 (Configuration)

## Decisions

### 1. Pipeline 引擎：asyncio.Task 并行 + 短路取消

**方案**：使用 `asyncio.create_task()` 为每个检测器创建独立任务，通过 `asyncio.wait(return_when=FIRST_COMPLETED)` 监控完成情况。检测到 `block` 时调用 `task.cancel()` 取消其余任务。`block_and_modify` 模式下 `modify` 也触发短路。

**为什么**：asyncio 原生支持任务取消，无需额外并发库。FIRST_COMPLETED 允许在第一个结果返回时立即检查 action，实现真正的短路。 cancelled 任务不会产生结果，避免资源浪费。

**备选方案及排除原因**：
- 备选 A：`asyncio.gather()` 一次性等待全部完成 — 不支持短路，必须等所有检测器完成
- 备选 B：`concurrent.futures.ThreadPoolExecutor` — 检测器是 async 的，线程池不适用
- 备选 C：第三方库（如 `anyio`）— 增加依赖，asyncio 已足够

### 2. DetectionResult / DetectionContext 定义位置

**方案**：在 `src/z_llm_safety_gateway/models.py` 中定义 DetectionResult 和 DetectionContext（Pydantic v2 模型），与现有 ExtractedContent/Modification 同文件。v0.5.0 提取到独立 SDK 包。

**为什么**：v0.2.0 不引入 SDK 包依赖，降低复杂度。模型定义在 gateway 内部允许直接使用 Pydantic v2 验证。v0.5.0 Plugin Ecosystem 阶段再提取。

**备选方案及排除原因**：
- 备选 A：立即创建 `z_llm_safety_gateway_sdk` 包 — v0.2.0 范围外，增加打包复杂度
- 备选 B：使用 dataclass 而非 Pydantic — 失去自动验证和 JSON 序列化

### 3. Detector ABC + 注册机制

**方案**：定义 `Detector` 抽象基类（async initialize/detect/health_check/shutdown），通过 `DetectorRegistry` 类管理注册。内置检测器在 `detectors/` 包中实现，通过硬编码注册表映射 name → class。v0.5.0 增加 entry points 发现。

**为什么**：MVP 只需内置检测器，硬编码注册表最简单可靠。统一的生命周期管理（initialize → detect → shutdown）确保资源正确释放。

**备选方案及排除原因**：
- 备选 A：entry points 自动发现 — v0.5.0 范围，MVP 不需要
- 备选 B：工厂函数而非 ABC — 失去类型检查和接口约束

### 4. 熔断器状态机

**方案**：实现 `CircuitBreaker` 类，三状态（CLOSED/OPEN/HALF_OPEN）。使用 `failure_count` 跟踪连续失败，`last_failure_time` 记录最后失败时间。HALF_OPEN 状态允许一次试探请求。状态转换通过 `before_call()` 和 `record_success()`/`record_failure()` 方法驱动。

**为什么**：纯 Python 实现，无外部依赖。状态机逻辑清晰，易于测试。与检测器配置解耦，通过组合方式使用。

**备选方案及排除原因**：
- 备选 A：`aiobreaker` 库 — 功能足够但增加依赖，自定义需求（fallback_action）需子类化
- 备选 B：装饰器模式 — 对检测器侵入性强，不利于测试

### 5. 阈值驱动决策引擎

**方案**：在 Pipeline 引擎中实现 `ThresholdDecisionEngine`，接收 DetectionResult.confidence 和检测器配置的 block_threshold/flag_threshold，输出最终 action。检测器自身只计算 confidence，不决定 action。

**为什么**：DESIGN.md Section 5.3 明确要求阈值与检测器逻辑分离。企业可在不修改检测器代码的情况下调整灵敏度。

**备选方案及排除原因**：
- 备选 A：检测器内部决定 action — 违反 DESIGN.md 设计决策 #5
- 备选 B：全局统一阈值 — 不同检测器需要不同灵敏度

### 6. 结果聚合策略

**方案**：`ResultAggregator` 类收集所有 DetectionResult，按规则聚合：final_action = max precedence (block > modify > flag > allow)；overall_risk_level = highest among all；modifications 按 priority 排序。可选 Flag 升级规则 DSL 求值。

**为什么**：聚合逻辑集中管理，易于测试和扩展。Flag 升级 DSL 在配置加载时预编译为求值函数，无运行时解析开销。

**备选方案及排除原因**：
- 备选 A：在 Pipeline 引擎中内联聚合 — 逻辑耦合，难以测试
- 备选 B：Python eval 执行 Flag 升级规则 — 安全风险

### 7. Flag 升级规则 DSL

**方案**：实现简单的表达式解析器，支持 `count`、`max_risk_level`、`categories` 变量，`>=`/`>`/`<=`/`<`/`==`/`!=` 运算符，`and`/`or` 逻辑（从左到右求值）。配置加载时解析为 AST，请求时求值。

**为什么**：DESIGN.md Section 5.6 明确要求非 Python eval 的 DSL。简单解析器足够 MVP 需求，避免安全风险。

**备选方案及排除原因**：
- 备选 A：Python eval + 沙箱 — 安全风险高
- 备选 B：正则匹配 — 表达能力不足，无法支持复杂条件

### 8. 敏感词检测：Aho-Corasick 自动机

**方案**：使用 `pyahocorasick` 库在检测器 initialize 时将词表编译为 Aho-Corasick 自动机，实现 O(n) 多模式匹配。支持多语言词表（通过 context.language 选择）和 exact/fuzzy 匹配模式。

**为什么**：DESIGN.md Section 5.9 和设计决策 #33 明确要求 Aho-Corasick。O(n) 时间复杂度与模式数量无关，适合大规模词表。pyahocorasick 是成熟的 C 扩展库。

**备选方案及排除原因**：
- 备选 A：正则表达式 alternation (word1|word2|...) — 词表大时性能差
- 备选 B：Trie 树手动实现 — 维护成本高，pyahocorasick 已优化

### 9. 毒性检测：transformers 懒加载

**方案**：使用 `transformers` 库加载 `unitary/toxic-bert` 模型。模型在首次 detect() 调用时懒加载（非 initialize 时），支持 offline_mode（跳过下载，要求模型已缓存）。模型推理在 CPU 上运行。

**为什么**：DESIGN.md Section 6.5 要求懒加载减少启动时间。offline_mode 支持 Docker 离线部署。unitary/toxic-bert 是广泛使用的开源毒性检测模型。

**备选方案及排除原因**：
- 备选 A：启动时加载 — 增加启动时间，未使用的检测器浪费资源
- 备选 B：API 调用外部服务 — 增加延迟和依赖，MVP 要求进程内
- 备选 C：使用更轻量的模型 — toxic-bert 已是较小模型（~110MB）

### 10. 配置系统重构

**方案**：`PipelineConfig.detectors` 从 `list[dict[str, Any]]` 改为 `DetectorsConfig` 模型，包含 `input: list[DetectorConfig]` 和 `output: list[DetectorConfig]`。`DetectorConfig` 扩展字段：`priority: int = 100`、`on_error: str = "fail_open"`、`circuit_breaker: CircuitBreakerConfig | None = None`、`config: dict[str, Any] = {}`（嵌套配置块，含 block_threshold/flag_threshold）。保留旧 `detectors: list[dict]` 字段作为废弃兼容（自动转换为新格式）。

**为什么**：DESIGN.md Section 10 要求 input/output 双向分组。嵌套 config 块允许不同检测器有不同配置 schema。保留旧字段兼容 v0.1.0 配置文件。

**备选方案及排除原因**：
- 备选 A：直接破坏性变更 — v0.1.0 配置文件无法使用
- 备选 B：使用 discriminated union — 过度复杂，config 是 dict 已足够灵活

### 11. 请求流集成

**方案**：修改 `routes/chat.py`，在 provider 转发前插入 input pipeline，在收到 response 后插入 output pipeline。流程：extract_content → language_detection → input_pipeline.run() → [block: return 400] / [modify: apply_modifications] / [allow: forward] → receive response → extract output content → output_pipeline.run() → [block: return 422] / [modify: apply to response] / [allow: return response]。SafetyHeadersMiddleware 从 request.state 读取 pipeline 结果动态设置响应头。

**为什么**：DESIGN.md Section 3.4/3.5 定义了此请求流。input pipeline 在转发前执行，output pipeline 在收到 response 后执行。非流式 sync 模式下 output 检测阻塞响应返回。

**备选方案及排除原因**：
- 备选 A：中间件层集成 — 中间件无法访问请求 body 和响应 body（已被消费）
- 备选 B：单独的 pipeline 路由 — 破坏 OpenAI API 兼容性

### 12. Block 错误响应格式

**方案**：返回 OpenAI 兼容错误格式，HTTP 400 (input block) / 422 (output block)，body 包含 `error` 标准字段 + `safety` 扩展字段（detector_name, category, risk_level, confidence, message）。

**为什么**：DESIGN.md Section 4.4 要求 OpenAI SDK 客户端可解析错误，同时应用可访问检测详情。HTTP 422 表示请求有效但响应内容不可接受。

**备选方案及排除原因**：
- 备选 A：自定义 JSON 格式 — OpenAI SDK 无法解析
- 备选 B：统一 400 — 语义不精确（input vs output block）

## Architecture

### 模块结构

```
src/z_llm_safety_gateway/
├── models.py                    # + DetectionResult, DetectionContext
├── config/
│   ├── models.py                # 重构: DetectorsConfig, DetectorConfig 扩展
│   └── validators.py            # 扩展: 新配置校验规则
├── pipeline/
│   ├── __init__.py
│   ├── engine.py                # PipelineEngine (并行执行 + 短路)
│   ├── aggregator.py            # ResultAggregator (结果聚合)
│   ├── threshold.py             # ThresholdDecisionEngine (阈值决策)
│   └── flag_escalation.py       # FlagEscalationRule (DSL 解析 + 求值)
├── detectors/
│   ├── __init__.py
│   ├── base.py                  # Detector ABC + DetectionContext
│   ├── registry.py              # DetectorRegistry (注册 + 生命周期)
│   ├── prompt_injection.py      # PromptInjectionDetector
│   ├── pii.py                   # PIIDetector
│   ├── toxicity.py              # ToxicityDetector
│   ├── sensitive_words.py       # SensitiveWordsDetector
│   └── secret_leak.py           # SecretLeakDetector
├── circuit_breaker/
│   ├── __init__.py
│   └── breaker.py               # CircuitBreaker (状态机)
├── language/
│   ├── __init__.py
│   └── detector.py              # LanguageDetector (langdetect 封装)
├── routes/
│   └── chat.py                  # 修改: 集成 pipeline
└── middleware/
    └── safety_headers.py        # 修改: 动态响应头
```

### 请求流（非流式 sync 模式）

```
Client Request
    │
    ▼
[RequestIDMiddleware] ── 生成/传播 request_id
    │
    ▼
[chat.py: POST /v1/chat/completions]
    │
    ├─ 1. extract_content(messages) → list[ExtractedContent]
    │
    ├─ 2. language_detection(text) → language (ISO 639-1)
    │
    ├─ 3. Input Pipeline:
    │     ├─ 为每个 ExtractedContent 创建 DetectionContext
    │     ├─ PipelineEngine.run(detectors, contexts)
    │     │   ├─ 并行启动所有 input 检测器
    │     │   ├─ 监控结果（FIRST_COMPLETED）
    │     │   ├─ block → 短路取消，返回 block 结果
    │     │   └─ 全部完成 → 聚合结果
    │     ├─ ThresholdDecisionEngine: confidence → action
    │     ├─ ResultAggregator: 聚合所有结果
    │     └─ FlagEscalationRule: 可选 flag → block 升级
    │
    ├─ 4a. final_action == block → 返回 400 + safety error
    ├─ 4b. final_action == modify → apply_modifications(request, modifications)
    ├─ 4c. final_action == flag/allow → 原样转发
    │
    ├─ 5. provider.forward_request(request) → response
    │
    ├─ 6. 提取 response content
    │
    ├─ 7. Output Pipeline:
    │     ├─ DetectionContext(direction="output")
    │     ├─ PipelineEngine.run(output_detectors, context)
    │     └─ 聚合结果
    │
    ├─ 8a. final_action == block → 返回 422 + safety error
    ├─ 8b. final_action == modify → 写回 response content
    └─ 8c. final_action == flag/allow → 返回 response
    │
    ▼
[SafetyHeadersMiddleware] ── X-Safety-Action / X-Safety-Risk-Level
    │
    ▼
Client Response
```

### Pipeline 引擎内部流程

```
PipelineEngine.run(detectors, contexts)
    │
    ├─ 对每个 context:
    │   ├─ 对每个 enabled detector:
    │   │   ├─ 检查 circuit_breaker (如有)
    │   │   │   ├─ OPEN → 跳过，fallback_action
    │   │   │   └─ CLOSED/HALF_OPEN → 执行
    │   │   ├─ asyncio.create_task(wrapped_detect())
    │   │   │   ├─ 记录 start_time
    │   │   │   ├─ detector.detect(content, context)
    │   │   │   ├─ 记录 duration_ms
    │   │   │   ├─ ThresholdDecisionEngine 决定 action
    │   │   │   └─ 异常 → on_error 策略
    │   │   └─ task → tasks set
    │   │
    │   ├─ asyncio.wait(tasks, return_when=FIRST_COMPLETED)
    │   │   ├─ 循环检查完成的 task
    │   │   ├─ action == block → cancel 其余 task, 短路
    │   │   ├─ action == modify + short_circuit_on=block_and_modify → 短路
    │   │   └─ 否则继续等待
    │   │
    │   └─ 全部完成 → ResultAggregator 聚合
    │
    └─ 返回 PipelineResult
         ├─ final_action
         ├─ overall_risk_level
         ├─ detector_results: list[DetectionResult]
         ├─ modifications: list[Modification]
         └─ pipeline_duration_ms
```

### 熔断器状态机

```
    ┌─────────┐  failure_count >= threshold  ┌─────────┐
    │ CLOSED  │ ──────────────────────────► │  OPEN   │
    └─────────┘                              └─────────┘
         ▲                                       │
         │ success                               │ recovery_timeout elapsed
         │                                       ▼
    ┌─────────┐  success                      ┌─────────┐
    │ CLOSED  │ ◄──────────────────────────── │HALF_OPEN│
    └─────────┘                                └─────────┘
                                                    │
                                                    │ failure
                                                    ▼
                                               ┌─────────┐
                                               │  OPEN   │
                                               └─────────┘
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| asyncio 任务取消不即时（检测器可能已执行部分工作） | 检测器应设计为可中断；取消后结果不收集 |
| 并行 modify 基于原始内容，位置偏移可能失效 | MVP 文档说明此限制；检测器返回完全修改后内容而非补丁 |
| transformers/torch 依赖较大（~2GB 安装体积） | 作为 optional dependencies；toxicity 检测器未安装时 fail_open |
| pyahocorasick 需要 C 编译 | Docker 镜像中预编译；本地开发用 pip install |
| 配置结构重构可能破坏现有 v0.1.0 测试 | 保留旧字段兼容；添加配置迁移测试 |
| 毒性检测器首次推理延迟（模型加载） | 懒加载 + 文档说明；可预热 |
| Flag 升级 DSL 解析器可能有边界 case | 配置加载时严格校验；全面的单元测试 |
