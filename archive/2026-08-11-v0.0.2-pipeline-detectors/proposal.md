# v0.2.0 - Pipeline & Detectors

## Why

v0.1.0 搭建了框架骨架（FastAPI server、配置系统、Provider 代理、内容提取器），但请求流是**纯透传**——没有任何安全检测能力。`extract_content()` 和 `apply_modifications()` 已实现但未接入请求流，`pipeline.detectors` 配置为空列表。

v0.2.0 需要实现 **Pipeline 引擎**和 **5 个 MVP 检测器**，使网关具备实际的内容安全检测能力：输入检测（block/modify/flag/allow）→ 转发 → 输出检测。同时需要**熔断器**保护外部检测器调用的稳定性。

## What Changes

- C1: 新建 Pipeline 引擎（并行执行 + 短路机制 + 结果聚合 + Flag 升级 DSL + 错误处理）
- C2: 新建检测器框架（Detector ABC + DetectionContext + DetectionResult + 注册机制）
- C3: 新建熔断器（Closed → Open → Half-Open 状态机）
- C4: 新建语言检测模块（langdetect）
- C5: 实现 Prompt Injection 检测器（规则 + 模式匹配）
- C6: 实现 PII 检测与脱敏检测器（正则模式，mask/replace/hash）
- C7: 实现毒性检测器（ML 模型 unitary/toxic-bert，懒加载 + 离线模式）
- C8: 实现敏感词过滤检测器（Aho-Corasick 自动机，多语言词表）
- C9: 实现密钥泄露检测器（正则模式）
- C10: 重构配置系统（检测器双向分组 + pipeline 配置扩展）
- C11: 集成 Pipeline 到请求流（input 检测 → 转发 → output 检测）

## Capabilities

### New Capabilities

- **pipeline-engine**：并行检测器执行引擎，短路机制，结果聚合，Flag 升级规则 DSL，错误处理
- **detector-framework**：Detector 抽象基类，DetectionContext/DetectionResult 数据模型，注册与生命周期管理
- **circuit-breaker**：熔断器状态机（Closed/Open/Half-Open），外部检测器故障保护
- **language-detection**：基于 langdetect 的语言检测，ISO 639-1 代码输出
- **prompt-injection-detector**：规则 + 模式匹配检测 Prompt Injection 攻击
- **pii-detector**：PII 检测与脱敏（正则模式，支持 mask/replace/hash）
- **toxicity-detector**：基于 ML 模型的毒性检测，阈值驱动决策
- **sensitive-words-detector**：Aho-Corasick 多模式匹配，多语言词表
- **secret-leak-detector**：密钥/凭据泄露正则检测

### Modified Capabilities

- **config-system**：检测器配置重构为 input/output 双向分组，pipeline 配置扩展
- **fastapi-server**：请求流集成 Pipeline（input 检测 → 转发 → output 检测）

## Impact

**代码层面**：
- 新增 ~20 个文件（pipeline/、detectors/、circuit_breaker/、language/ 模块）
- 修改 ~5 个文件（config/models.py、config/validators.py、routes/chat.py、middleware/safety_headers.py、app.py）
- 预估 ~3000+ 行新增代码

**配置层面**：
- `gateway.yaml` 结构重构：`detectors` 改为 `{input: [...], output: [...]}`，每个 detector 增加 `priority`/`on_error`/`circuit_breaker`/`config` 字段
- `pipeline` 增加 `short_circuit_on`/`flag_escalation`/`output_detection` 配置
- 新增 `model_cache` 全局配置

**基础设施**：
- 新增依赖：`langdetect`、`pyahocorasick`、`transformers`、`torch`（CPU）
- ML 模型首次使用时从 HuggingFace Hub 下载（~100-500MB）

## Constraints

- MVP 仅支持非流式 sync 模式（流式在 v0.3.0）
- 不实现 gRPC sidecar 检测器和进程内插件 entry points 发现（v0.5.0）
- DetectionResult/Modification 定义在 gateway 内部（非独立 SDK 包，v0.5.0 提取）
- PII 检测器 MVP 使用正则模式，Microsoft Presidio 集成为可选增强
- Prompt Injection 检测器 MVP 使用规则 + 模式匹配，ML 模型增强留待后续
- ML 模型依赖较重（transformers + torch），需支持懒加载和离线模式

## Stakeholders

- 网关使用者（应用程序开发者）
- 安全检测器开发者
- 系统运维工程师

## Risk Areas

- capability: pipeline-engine — 并发执行 + 短路取消的竞态条件（缓解：asyncio.Task 管理 + cancellation）
- capability: toxicity-detector — ML 模型下载失败/加载超时（缓解：懒加载 + fail_open + offline_mode）
- capability: config-system — 配置结构重构破坏 v0.1.0 向后兼容（缓解：兼容旧字段 + 迁移测试）
- capability: fastapi-server — 请求流集成引入延迟（缓解：并行执行 + 短路 + 超时控制）

## NonGoals

- 流式 SSE 检测（v0.3.0）
- 滑动窗口检测（v0.3.0）
- 后审计检测（v0.3.0）
- 审计日志记录（v0.3.0）
- gRPC sidecar 检测器（v0.5.0）
- 进程内插件 entry points 发现（v0.5.0）
- 检测器 SDK 独立包（v0.5.0）
- 认证/限流/TLS（v0.4.0）

## Critical

- [x] 非关键变更（默认）

## Risk Assessment

- **safety_critical**：false
- **financial**：false
- **cross_system**：false

## Anchoring

- **level**：L1（行为锚定）
- **reference_changes**：2026-08-11-v0.1.0-framework-skeleton

## Success Criteria

- [ ] Pipeline 引擎并行执行多个检测器，任一 block 时短路取消其余检测器
- [ ] 5 个 MVP 检测器各自正确检测对应风险类型
- [ ] 阈值驱动决策：confidence >= block_threshold → block，flag_threshold <= confidence < block_threshold → flag
- [ ] 检测器优先级决定 modify 应用顺序（priority 数字越小越先应用）
- [ ] 熔断器在连续失败后打开，恢复超时后半开试探
- [ ] 语言检测结果存入 DetectionContext.language（ISO 639-1）
- [ ] 请求流集成：input 检测 → block(400)/modify/allow → 转发 → output 检测 → block(422)/modify/allow
- [ ] Block 时返回 OpenAI 兼容错误响应（含 safety 扩展字段）
- [ ] 配置校验规则全部生效
- [ ] fail_open/fail_closed 错误处理策略正确执行
- [ ] 全量测试通过，ruff/mypy 无错误
