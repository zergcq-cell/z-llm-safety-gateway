# audit-logger — 行为规格（Human View）

> **Change**: 2026-08-12-v0.4.0-security-observability
> **Capability**: audit-logger
> **Created**: 2026-08-12T17:00:00+08:00
> **Confidence**: high
> **类型**: 修正类（backlog B-08 / B-09，design Decision 15）

## Description

本 capability 修正审计日志（Audit Logger）在 v0.3.0 中的字段失真问题（backlog **B-09**），并落实同步输出检测的 pipeline 级超时强制（backlog **B-08**），与 DESIGN.md 12.1（审计 schema）及 3.5（`sync_timeout` 行为）对齐。具体包括：

- 补齐 `total_duration_ms` 赋值（消除全项目恒 0 的赋值点）。
- 从请求体 `user` 字段提取 `user_id`。
- 为 `DetectorAuditRecord` 填充 `duration_ms` / `error`（不再用默认占位）。
- 统一流式 `post_audit` 字典 schema 为 `result` / `category` / `risk_level`（DESIGN 12.1），移除 `effective_action` / `original_action` 旧键。
- 为 `DetectorAuditRecord` 增加可选 `applied` 字段；流式 `modify` 因响应已发出而无法应用时降级为 `flag` 并置 `applied: false`（DESIGN 8.4）。
- 非流式同步输出检测用 `asyncio.wait_for` 包裹 `engine.run`，强制 `sync_timeout`（DESIGN 3.5）。

审计日志是合规追溯的唯一依据，必须如实反映输入/输出两侧的实际检测结果与耗时。

---

## Requirements

### REQ-AUDIT-001: 补齐审计条目 total_duration_ms 赋值

**Description**: 为 input/output 审计条目补齐 `total_duration_ms`，消除恒 0 赋值点，真实反映各 phase 总耗时。

**Confidence**: high

#### SC-AUDIT-001: input 条目 total_duration_ms 实测赋值

- **Given**: 一次非流式 chat 请求，启用审计，走输入 pipeline 并转发 provider
- **When**: 构建 input 审计条目时
- **Then**: input 条目的 `total_duration_ms` **SHALL** 为从请求进入时刻到输入 pipeline 完成（block 响应发出或请求转发 provider）之间的实测耗时（ms），且 **SHALL** 恒大于等于 0
- **And**:
  - 该值 **SHALL** 反映真实计时，而非占位 0（消除 B-09 所述全项目无赋值点问题）

#### SC-AUDIT-002: output 条目 total_duration_ms 实测赋值

- **Given**: 一次非流式 chat 请求，输出 pipeline 完成并返回响应
- **When**: 构建 output 审计条目时
- **Then**: output 条目的 `total_duration_ms` **SHALL** 为从 LLM 响应收到到输出响应发送给客户端（block/修改/未修改响应）之间的实测耗时（ms）
- **And**:
  - 该值 **SHALL** 排除 LLM provider 延迟

#### SC-AUDIT-003: total_duration_ms 不再恒为 0

- **Given**: 审计条目被序列化为 JSONL
- **When**: 输出 audit.log 中的 `total_duration_ms` 字段
- **Then**: `total_duration_ms` **SHALL** 已被正确赋值（不再恒为 0）

---

### REQ-AUDIT-002: 从请求提取 user_id 填入审计条目

**Description**: 从请求体顶层 `user` 字段提取 `user_id` 填入审计条目；缺省时为 `null`。

**Confidence**: high

#### SC-AUDIT-004: 请求体含 user 字段时提取

- **Given**: chat 请求体包含顶层 `'user'` 字段（如 `'user_001'`）
- **When**: 构建该请求的 input 与 output 审计条目时
- **Then**: 条目的 `user_id` **SHALL** 等于请求体 `'user'` 字段的值（`'user_001'`）

#### SC-AUDIT-005: 请求体无 user 字段时为 null

- **Given**: chat 请求体未包含顶层 `'user'` 字段
- **When**: 构建该请求的 input 与 output 审计条目时
- **Then**: 条目的 `user_id` **SHALL** 为 `null`（可选字段，缺省不伪造）

---

### REQ-AUDIT-003: DetectorAuditRecord 填充 duration_ms / error

**Description**: `_build_audit_entry` 从 `DetectionResult` 填充 `duration_ms` / `error`，不再用默认占位。

**Confidence**: high

#### SC-AUDIT-006: duration_ms 取检测器实测值

- **Given**: 一个检测器成功执行并返回 DetectionResult（含实测 duration_ms）
- **When**: routes/chat.py 的 `_build_audit_entry` 将该结果写入 detectors 数组
- **Then**: 对应 DetectorAuditRecord 的 `duration_ms` **SHALL** 取该 DetectionResult 的 `duration_ms`
- **And**:
  - 该值 **SHALL** 反映真实单检测器耗时，而非默认 0.0

#### SC-AUDIT-007: error 取检测器异常信息

- **Given**: 一个检测器执行异常并返回带 error 信息的 DetectionResult
- **When**: routes/chat.py 的 `_build_audit_entry` 将该结果写入 detectors 数组
- **Then**: 对应 DetectorAuditRecord 的 `error` **SHALL** 取该 DetectionResult 的 error 信息（非 null）
- **And**:
  - 检测器执行成功时 `error` **SHALL** 为 null

---

### REQ-AUDIT-004: 统一 post_audit 字典 schema 与 DESIGN 12.1 一致

**Description**: 流式 `post_audit` 字典统一为 `result` / `category` / `risk_level`（DESIGN 12.1），移除 `effective_action` / `original_action` 旧键。

**Confidence**: high

#### SC-AUDIT-008: post-audit 执行后使用新 schema

- **Given**: 流式滑动窗口模式，post-audit 已执行并返回 outcome
- **When**: 构建 output 审计条目的 `post_audit` 字典时
- **Then**: `post_audit` **SHALL** 为 `{'executed': true, 'result': <outcome.effective_action>, 'category': <outcome.category>, 'risk_level': <outcome.risk_level>}`
- **And**:
  - `result` 键 **SHALL** 取 `outcome.effective_action` 的值
  - `category` 键 **SHALL** 取 `outcome.category` 的值（可为空字符串）
  - `risk_level` 键 **SHALL** 取 `outcome.risk_level` 的值

#### SC-AUDIT-009: 不再使用旧键名

- **Given**: 流式 post-audit 执行后构建 `post_audit` 字典
- **When**: 检查 `post_audit` 字典的键名
- **Then**: `post_audit` 字典 **SHALL NOT** 再使用 `effective_action` / `original_action` 作为键名（统一为 `result`）

#### SC-AUDIT-010: post-audit 跳过/buffer 模式

- **Given**: 流式 buffer 模式，或 streaming 配置 `post_audit=false`（post-audit 被跳过）
- **When**: 构建 output 审计条目的 `post_audit` 字典时
- **Then**: `post_audit` **SHALL** 为 `{'executed': false}`（不含 result/category/risk_level）

---

### REQ-AUDIT-005: DetectorAuditRecord 增加可选 applied 字段，流式 modify 降级置 false

**Description**: 为 `DetectorAuditRecord` 增加可选 `applied` 字段；流式 post-audit 中 `modify` 因响应已发出无法应用时降级为 `flag` 并置 `applied: false`（DESIGN 8.4）。

**Confidence**: high

#### SC-AUDIT-011: 模型含可选 applied 字段

- **Given**: audit/models.py 的 `DetectorAuditRecord` 模型
- **When**: 定义审计记录字段时
- **Then**: `DetectorAuditRecord` **SHALL** 新增可选字段 `applied`（bool，默认缺省/None），向后兼容既有序列化

#### SC-AUDIT-012: 流式 modify 降级并置 applied=false

- **Given**: 流式 post-audit 中某检测器返回 `action='modify'`（响应已流式发出，无法应用）
- **When**: 构建该检测器的 `DetectorAuditRecord` 时
- **Then**: 该记录 **SHALL** 记录 `action='flag'`（modify 降级）且 `applied=false`
- **And**:
  - 该降级事实 **SHALL** 在审计日志中如实记录（`applied:false`）

#### SC-AUDIT-013: 已应用的 modify 记录 applied=true

- **Given**: 输入侧或非流式同步输出检测的 modify 已成功写回请求/响应
- **When**: 构建对应 `DetectorAuditRecord` 时
- **Then**: 该记录 **SHALL** 记录 `action='modify'` 且 `applied=true`（或省略 applied 表示已应用）

---

### REQ-AUDIT-006: 非流式同步输出检测加 asyncio.wait_for 强制 sync_timeout

**Description**: 非流式同步输出检测的 `engine.run` 用 `asyncio.wait_for` 包裹，强制 pipeline 级 `sync_timeout`（DESIGN 3.5，backlog B-08）。

**Confidence**: high

#### SC-AUDIT-014: 同步输出检测被 wait_for 包裹

- **Given**: 非流式（`stream=false`）同步输出检测，输出检测器已配置且 engine 可用
- **When**: 调用 `engine.run(output_detectors, [context], configs)` 做同步输出检测
- **Then**: 该调用 **SHALL** 被 `asyncio.wait_for(..., timeout=sync_timeout)` 包裹，`sync_timeout` 为 pipeline 级超时
- **And**:
  - `sync_timeout` 超时后 **SHALL** 停止等待未完成的检测器

#### SC-AUDIT-015: 超时后未完成检测器按 on_error 处理

- **Given**: `asyncio.wait_for` 因 `sync_timeout` 触发 `asyncio.TimeoutError`
- **When**: 处理输出检测超时
- **Then**: 对未完成检测器 **SHALL** 按各检测器 `on_error` 策略处理（fail_open 跳过该结果；fail_closed 视为 block）
- **And**:
  - 已完成的检测器结果 **SHALL** 正常聚合，最终 action 由聚合结果决定

#### SC-AUDIT-016: sync_timeout 未配置时使用默认 5s

- **Given**: `sync_timeout` 未在配置中显式设置
- **When**: 计算同步输出检测的 pipeline 级超时
- **Then**: `sync_timeout` **SHALL** 使用默认值（DESIGN 3.5 定义 `sync_timeout: 5s`）

---

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-AUDIT-001 / 003 | input 条目 total_duration_ms 真实赋值 |
| CP-2 | SC-AUDIT-002 | output 条目 total_duration_ms 真实赋值且排除 provider 延迟 |
| CP-3 | SC-AUDIT-004 | 请求体含 user 字段时 user_id 被提取 |
| CP-4 | SC-AUDIT-005 | 请求体无 user 字段时 user_id 为 null |
| CP-5 | SC-AUDIT-006 | DetectorAuditRecord 填充 duration_ms |
| CP-6 | SC-AUDIT-007 | DetectorAuditRecord 填充 error |
| CP-7 | SC-AUDIT-008 | post_audit 使用 result/category/risk_level schema |
| CP-8 | SC-AUDIT-009 | post_audit 不再使用旧键名 |
| CP-9 | SC-AUDIT-010 | post-audit 跳过/buffer 模式为 {'executed': false} |
| CP-10 | SC-AUDIT-011 | DetectorAuditRecord 含可选 applied 字段 |
| CP-11 | SC-AUDIT-012 | 流式 modify 降级为 flag 且 applied=false |
| CP-12 | SC-AUDIT-013 | 已应用 modify 记录 applied=true |
| CP-13 | SC-AUDIT-014 | 同步输出检测被 asyncio.wait_for(sync_timeout) 包裹 |
| CP-14 | SC-AUDIT-015 | 超时后未完成检测器按 on_error 处理 |
| CP-15 | SC-AUDIT-016 | sync_timeout 默认 5s |
| CP-16 | -- | ruff lint 通过 |
| CP-17 | -- | mypy 类型检查通过 |

## Evidence 索引

| Scenario | 证据来源 |
|----------|----------|
| SC-AUDIT-001 ~ 003 | backlog B-09；design Decision 15；DESIGN 12.1 `total_duration_ms` |
| SC-AUDIT-004 ~ 005 | backlog B-09；design Decision 15；DESIGN 12.1 `user_id` |
| SC-AUDIT-006 ~ 007 | backlog B-09；design Decision 15；DESIGN 12.1 `detectors.duration_ms` / `error` |
| SC-AUDIT-008 ~ 010 | backlog B-09；design Decision 15；DESIGN 12.1 `post_audit` |
| SC-AUDIT-011 ~ 013 | backlog B-09；design Decision 15；DESIGN 8.4 流式 modify 降级 |
| SC-AUDIT-014 ~ 016 | backlog B-08；design Decision 15；DESIGN 3.5 `sync_timeout` |
