# v0.2.0 任务清单

## 1. config-system 重构（P0）

- [x] 1.1 重构 `src/z_llm_safety_gateway/config/models.py` — DetectorsConfig (input/output 双向分组), DetectorConfig 扩展 (priority/on_error/circuit_breaker/config), CircuitBreakerConfig, PipelineConfig 扩展 (short_circuit_on/flag_escalation/sync_timeout), ModelCacheConfig
- [x] 1.2 扩展 `src/z_llm_safety_gateway/config/validators.py` — 阈值校验、未知检测器校验、word_list_file 缺失校验、flag_escalation.rule 语法校验、旧格式兼容转换
- [x] 1.3 更新 `config/gateway.yaml` — 添加 v0.2.0 示例配置（detectors input/output、pipeline 扩展、model_cache）
- [x] 1.4 编写测试 `tests/unit/config/test_v2_models.py` — TC-CONF-001~011（双向分组、扩展字段、阈值校验、旧格式兼容）
- [x] 1.5 编写测试 `tests/unit/config/test_v2_validators.py` — TC-CONF-012~024（未知检测器、缺失文件、flag_escalation 语法、gRPC 预留校验）

## 2. detector-framework（P0）

- [x] 2.1 扩展 `src/z_llm_safety_gateway/models.py` — DetectionResult (detector_name/category/action/confidence/risk_level/message/details/modified_content/duration_ms/error) + DetectionContext (direction/request_id/user_id/metadata/language/message_index)
- [x] 2.2 创建 `src/z_llm_safety_gateway/detectors/base.py` — Detector ABC (name/category/description/version 属性 + async initialize/detect/health_check/shutdown 方法)
- [x] 2.3 创建 `src/z_llm_safety_gateway/detectors/registry.py` — DetectorRegistry (注册内置检测器 name→class 映射、create_instance、initialize_all、shutdown_all)
- [x] 2.4 创建 `src/z_llm_safety_gateway/detectors/__init__.py` — 包初始化 + 导出 + create_default_registry()
- [x] 2.5 编写测试 `tests/unit/detectors/test_base.py` — TC-DFRK-001~005 (Detector ABC 接口、生命周期方法)
- [x] 2.6 编写测试 `tests/unit/detectors/test_models.py` — TC-DFRK-006~007 (DetectionResult/DetectionContext 模型验证)
- [x] 2.7 编写测试 `tests/unit/detectors/test_registry.py` — TC-DFRK-008~009 (注册、查找、生命周期管理)

## 3. circuit-breaker（P0）

- [x] 3.1 创建 `src/z_llm_safety_gateway/circuit_breaker/breaker.py` — CircuitBreaker (CLOSED/OPEN/HALF_OPEN 状态机, failure_count, last_failure_time, before_call/record_success/record_failure 方法)
- [x] 3.2 创建 `src/z_llm_safety_gateway/circuit_breaker/__init__.py` — 包初始化 + 导出
- [x] 3.3 编写测试 `tests/unit/circuit_breaker/test_breaker.py` — TC-CB-001~009 (三状态转换、failure_threshold、recovery_timeout、fallback_action)

## 4. pipeline-engine（P0）

- [x] 4.1 创建 `src/z_llm_safety_gateway/pipeline/threshold.py` — ThresholdDecisionEngine (confidence + block_threshold/flag_threshold → action)
- [x] 4.2 创建 `src/z_llm_safety_gateway/pipeline/aggregator.py` — ResultAggregator (final_action 优先级聚合、overall_risk_level、modifications 排序、risk_profile)
- [x] 4.3 创建 `src/z_llm_safety_gateway/pipeline/flag_escalation.py` — FlagEscalationRule (DSL 解析器: count/max_risk_level/categories + 运算符 + and/or)
- [x] 4.4 创建 `src/z_llm_safety_gateway/pipeline/engine.py` — PipelineEngine (asyncio.Task 并行、FIRST_COMPLETED 短路、circuit_breaker 集成、on_error 策略、timeout、pipeline_duration_ms)
- [x] 4.5 创建 `src/z_llm_safety_gateway/pipeline/__init__.py` — 包初始化 + 导出
- [x] 4.6 编写测试 `tests/unit/pipeline/test_threshold.py` — TC-PIPE-001~003 (阈值决策)
- [x] 4.7 编写测试 `tests/unit/pipeline/test_aggregator.py` — TC-PIPE-004~006 (结果聚合、修改排序)
- [x] 4.8 编写测试 `tests/unit/pipeline/test_flag_escalation.py` — TC-PIPE-007 (DSL 解析与求值)
- [x] 4.9 编写测试 `tests/unit/pipeline/test_engine.py` — TC-PIPE-008~015 (并行执行、短路、错误处理、超时、duration)

## 5. language-detection（P0）

- [x] 5.1 创建 `src/z_llm_safety_gateway/language/detector.py` — LanguageDetector (langdetect 封装, detect_language(text) → ISO 639-1 | None)
- [x] 5.2 创建 `src/z_llm_safety_gateway/language/__init__.py` — 包初始化 + 导出
- [x] 5.3 编写测试 `tests/unit/language/test_detector.py` — TC-LANG-001~007 (语言检测、ISO 代码、空文本、异常处理)

## 6. prompt-injection-detector（P1）

- [x] 6.1 创建 `src/z_llm_safety_gateway/detectors/prompt_injection.py` — PromptInjectionDetector (正则模式列表, initialize 编译, detect 计算置信度)
- [x] 6.2 编写测试 `tests/unit/detectors/test_prompt_injection.py` — TC-INJ-001~012 (模式检测、置信度、阈值决策、中英文)

## 7. pii-detector（P1）

- [x] 7.1 创建 `src/z_llm_safety_gateway/detectors/pii.py` — PIIDetector (email/phone/ssn/credit_card/ip_address 正则, mask/replace/hash 脱敏, action=modify)
- [x] 7.2 编写测试 `tests/unit/detectors/test_pii.py` — TC-PII-001~013 (PII 检测、脱敏模式、entity_types 配置、details 记录)

## 8. sensitive-words-detector（P1）

- [x] 8.1 创建 `src/z_llm_safety_gateway/detectors/sensitive_words.py` — SensitiveWordsDetector (pyahocorasick 自动机, 多语言词表, exact/fuzzy 匹配)
- [x] 8.2 创建测试词表文件 `tests/fixtures/sensitive_en.txt` 和 `tests/fixtures/sensitive_zh.txt`
- [x] 8.3 编写测试 `tests/unit/detectors/test_sensitive_words.py` — TC-SW-001~016 (Aho-Corasick 匹配、多语言、exact/fuzzy、词表加载、文件缺失报错)

## 9. secret-leak-detector（P1）

- [x] 9.1 创建 `src/z_llm_safety_gateway/detectors/secret_leak.py` — SecretLeakDetector (api_key/aws_secret/private_key/jwt_token 正则, action=block)
- [x] 9.2 编写测试 `tests/unit/detectors/test_secret_leak.py` — TC-SEC-001~013 (密钥检测、patterns 配置、自定义正则、details 记录)

## 10. toxicity-detector（P1）

- [x] 10.1 创建 `src/z_llm_safety_gateway/detectors/toxicity.py` — ToxicityDetector (transformers 懒加载, offline_mode, model_cache_dir/model_version, 阈值决策)
- [x] 10.2 编写测试 `tests/unit/detectors/test_toxicity.py` — TC-TOX-001~016 (模型加载、懒加载、offline_mode、阈值决策、错误处理) — 使用 mock 模拟 transformers
- [x] 10.3 更新 `pyproject.toml` — 添加 optional dependencies: transformers, torch, langdetect, pyahocorasick

## 11. fastapi-server 集成（P0）

- [x] 11.1 修改 `src/z_llm_safety_gateway/routes/chat.py` — 集成 input pipeline (extract → language detect → pipeline run → block/modify/allow → forward) + output pipeline (extract → pipeline run → block/modify/allow → return)
- [x] 11.2 修改 `src/z_llm_safety_gateway/middleware/safety_headers.py` — 动态 X-Safety-Action (从 request.state 读取 pipeline 结果) + X-Safety-Risk-Level
- [x] 11.3 修改 `src/z_llm_safety_gateway/app.py` — 初始化 DetectorRegistry + PipelineEngine, 存入 app.state
- [x] 11.4 扩展 `src/z_llm_safety_gateway/exceptions.py` — SafetyBlockError (含 detector_name/category/risk_level/confidence/message) + safety 扩展字段序列化
- [x] 11.5 编写测试 `tests/unit/routes/test_chat_pipeline.py` — TC-FAST-001~006 (input/output pipeline 集成、block 400/422、modify 写回)
- [x] 11.6 编写测试 `tests/unit/middleware/test_safety_headers_v2.py` — TC-FAST-007~008 (动态响应头)
- [x] 11.7 编写测试 `tests/integration/test_pipeline_flow.py` — TC-FAST-009~012 (完整请求流、无检测器透传、safety 扩展字段、pipeline 结果存储)
- [x] 11.8 编写测试 `tests/integration/test_block_response.py` — TC-FAST-013 (Block 错误响应格式验证)

## 12. 测试与验证

- [x] 12.1 全量 pytest 通过（v0.1.0 回归 + v0.2.0 新测试）— 544 passed
- [x] 12.2 `ruff check src/ tests/` 无错误 — All checks passed
- [x] 12.3 `mypy src/` 无错误 — Success: no issues found in 42 source files
- [x] 12.4 更新 `config/gateway.yaml` 完整示例配置
- [x] 12.5 更新 `pyproject.toml` 依赖版本
