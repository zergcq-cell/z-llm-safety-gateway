# v0.3.0 Streaming & Audit — 设计调整记录

> 版本：v0.3.0
> 创建日期：2026-08-12
> 对应 Phase 2 Spec：design.md

## 调整 1：to_json_line() 返回类型修正

| 字段 | 内容 |
|------|------|
| **影响级别** | Low |
| **影响范围** | audit/models.py, audit/logger.py |
| **原设计** | `AuditEntry.to_json_line() -> str`，返回 JSON 字符串 |
| **实际实现** | `AuditEntry.to_json_line() -> dict[str, Any]`，返回 dict；由 logger 负责序列化 |
| **原因** | logger 需要在序列化前对 content 字段做 pop/sanitize 操作，必须操作 dict 而非 str |
| **兼容性** | 内部 API，无外部影响 |

## 调整 2：_build_file_handler 返回类型修正

| 字段 | 内容 |
|------|------|
| **影响级别** | Low |
| **影响范围** | audit/logger.py |
| **原设计** | `_build_file_handler() -> logging.Handler` |
| **实际实现** | `_build_file_handler() -> logging.Handler | None`，目录创建失败时返回 None |
| **原因** | 原设计已包含目录创建失败的降级逻辑（降级到 stdout），但返回类型未标注 Optional |
| **兼容性** | 调用方已有 None 检查（`if self._file_handler is not None`） |

## 调整 3：stream_forward 返回类型标注

| 字段 | 内容 |
|------|------|
| **影响级别** | Low |
| **影响范围** | providers/base.py |
| **原设计** | `stream_forward()` 无返回类型标注 |
| **实际实现** | `stream_forward() -> AsyncIterator[str]` |
| **原因** | async generator 需要明确的返回类型标注以通过 mypy 严格检查 |
| **兼容性** | 子类实现不受影响 |

## 调整 4：_build_audit_entry direction 参数类型收紧

| 字段 | 内容 |
|------|------|
| **影响级别** | Low |
| **影响范围** | routes/chat.py |
| **原设计** | `_build_audit_entry(direction: str, ...)` |
| **实际实现** | `_build_audit_entry(direction: Literal["input", "output"], ...)` |
| **原因** | AuditEntry.direction 字段为 `Literal["input", "output"]`，参数类型应匹配 |
| **兼容性** | 所有调用方已传入 "input" 或 "output" 字面量 |

## 调整 5：ThresholdDecisionEngine 与检测器内部阈值共用 config key

| 字段 | 内容 |
|------|------|
| **影响级别** | Medium |
| **影响范围** | pipeline/engine.py, detectors/sensitive_words.py |
| **原设计** | 检测器自行决定 action（block/flag/allow），engine 仅聚合 |
| **实际实现** | engine 的 `ThresholdDecisionEngine.decide()` 用 config 中的 `block_threshold`/`flag_threshold` 作为 confidence 阈值，覆盖检测器返回的 action |
| **原因** | DESIGN.md Section 5.3 要求"分离 confidence 计算和 action 决策"，engine 统一做阈值决策。但 SensitiveWordsDetector 内部也使用同名字段做 count-based 阈值，导致 config key 共用 |
| **影响** | SensitiveWordsDetector 的 count-based block_threshold/flag_threshold 被 engine 误读为 confidence 阈值。当 block_threshold=3（count）时，engine 将 confidence=1.0 与 3.0 比较，导致 block 被降级 |
| **缓解措施** | 当前通过合理设置 confidence 值规避（block → confidence=1.0, flag → confidence=0.5, allow → confidence=0.0）。若需 count-based 阈值生效，应在检测器 config 中使用不同 key 名称（如 `count_block_threshold`） |
| **后续建议** | v0.4.0 或后续版本考虑分离 config key 命名空间 |
