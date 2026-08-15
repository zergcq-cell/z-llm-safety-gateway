# sse-streaming — 行为规格（Human View）

> **变更**: 2026-08-12-v0.4.0-security-observability
> **Capability**: sse-streaming（修正类）
> **创建时间**: 2026-08-12T16:00:00+08:00
> **置信度**: high
> **关联能力**: fastapi-server、config-system（依赖 streaming_config）

---

## 1. 概述

本 capability 为**修正类**，修复 v0.3.0 流式 SSE 检测与审计的三类正确性缺陷，覆盖 backlog **B-03 / B-05 / B-06 / B-07**，依据 design **Decision 14（SSE 分片重组）** 与 **Decision 15（流式审计字段修正）**。

| 修正点 | Backlog | 设计 | 现状问题 |
|--------|---------|------|----------|
| SSE 分片行缓冲重组（SSEBuffer） | B-03 | Decision 14 | `aiter_text()` 不保证事件完整落在单 chunk，`_extract_delta_text` 要求 `chunk.startswith("data:")`，分片窗口漏检 |
| 输出侧 `output_action`/`output_risk_level` 单独维护 | B-05 | Decision 15 | 流式输出审计 `final_action` 错取输入侧 `request.state.safety_action`；流中阻断仍记录 allow |
| 后审计 `detector_results` 与 `window_count` 写入审计 | B-06 | Decision 15 | `detectors` 恒空；`window_count` 恒为占位 0 |
| `PostAuditRunner` 与 handler 透传 `request_id` 与输入侧 `language` | B-07 | Decision 15 / DESIGN 6.6 | `PostAuditRunner.run` 硬编码 `request_id=""`；handler 上下文不含 language |

设计依据：design.md Decision 14 / 15；DESIGN.md 8.2（滑动窗口与 action 表）、12.1（审计 schema）、6.6（语言复用）。

---

## 2. 需求与场景

### REQ-SSE-001 — SSE 分片行缓冲重组（B-03 / Decision 14）

`streaming/sse.py` 新增 `SSEBuffer`，按 `\n\n` 边界缓存不完整事件，跨 chunk 拼接完整后再交给 `_extract_delta_text`，消除分片漏检。

#### SC-SSE-001（high）：单个 data 事件跨 chunk 拆分时重组

- **Given**: provider 经 `stream_forward` 的 `aiter_text()` 按网络分片 yield，单个 `data:{json}\n\n` 事件被拆散到两个相邻 chunk
- **When**: SSEBuffer 接收第一段不完整事件后接收第二段补齐 `\n\n` 边界
- **Then**: SSEBuffer **SHALL** 在 `\n\n` 边界处重组出完整 SSE 事件，并交给 `_extract_delta_text` 解析出 delta 文本
- **And**:
  - 重组后事件 **SHALL** 与原始事件完全一致，不丢失、不重复任何字节
  - 该 delta 文本 **SHALL** 进入滑动窗口检测，不再因分片判为空窗口

#### SC-SSE-002（high）：单 chunk 多完整事件按 `\n\n` 切分

- **Given**: 单个 chunk 内含多个以 `\n\n` 分隔的完整 SSE 事件
- **When**: SSEBuffer 处理该 chunk
- **Then**: SSEBuffer **SHALL** 一次性产出全部完整事件并按原始顺序交付
- **And**:
  - 事件分界 **SHALL** 严格以 `\n\n` 为准，不以行数或固定长度猜测

#### SC-SSE-003（medium）：末尾残留 flush 不丢内容

- **Given**: 流接近结束，缓冲区内残留一段未以 `\n\n` 结尾的不完整事件
- **When**: `stream_forward` 迭代完毕进入结束处理
- **Then**: SSEBuffer **SHALL** 在结束时 flush 残留内容并解析，避免末尾分片内容静默丢弃导致漏检
- **And**:
  - 若残留确为完整 JSON 负载，**SHALL** 仍被检测并透传
  - 若为协议终止标记（如 `[DONE]`），**SHALL** 透传且不引发解析异常

#### SC-SSE-004（high）：非 data 事件透传不受影响

- **Given**: 流中出现非 data 事件（如 `event: safety_block`、`data: [DONE]`）
- **When**: 这些事件被跨 chunk 拆分或与 data 事件混在同一 chunk
- **Then**: SSEBuffer **SHALL** 按 `\n\n` 边界正确切分并原样透传，不改变类型与负载
- **And**:
  - 安全事件与终止标记 **SHALL** 不受缓冲重组影响，保持客户端可识别

---

### REQ-SSE-002 — 输出侧 `output_action`/`output_risk_level` 单独维护（B-05 / Decision 15）

流式输出审计应如实反映输出侧滑动窗口/后置审计的真实结果，而非输入侧 `request.state.safety_action`。

#### SC-SSE-005（high）：handler 独立维护输出侧状态

- **Given**: StreamingHandler 在滑动窗口模式运行，逐窗口执行输出侧检测
- **When**: 每个窗口产生 PipelineResult
- **Then**: handler **SHALL** 独立维护输出侧 `output_action` 与 `output_risk_level`（取自滑动窗口 `final_action` / `overall_risk_level`）
- **And**:
  - `output_action` **SHALL** 随每次检测结果按严重度升序聚合（allow < flag < modify < block）
  - `output_risk_level` **SHALL** 取所有已检测窗口的最高风险等级

#### SC-SSE-006（high）：流中被阻断时审计记录 block

- **Given**: 流式检测途中某个窗口 `final_action == block`
- **When**: handler 发出 `safety_block` 事件并停止透传
- **Then**: 输出侧 `output_action` **SHALL** 置为 block，`output_risk_level` 取阻断窗口风险等级，并记录触发 detector 与 category
- **And**:
  - 最终审计条目 **SHALL** 记录 `final_action=block` 及对应 `blocked_by` / `category` / `confidence` / `reason`

#### SC-SSE-007（high）：输出侧审计不再读取输入侧

- **Given**: 同一请求的输入侧 `request.state.safety_action` 与输出侧检测结果可能不同
- **When**: 构建流式输出审计条目
- **Then**: 流式输出审计 **SHALL** 使用输出侧 `output_action` / `output_risk_level`，不再读取输入侧 `request.state.safety_action`
- **And**:
  - 当输出侧被阻断而输入侧为 allow 时，审计 **SHALL** 记录 block 而非 allow

---

### REQ-SSE-003 — 后审计 `detector_results` 与 `window_count` 写入审计（B-06 / Decision 15）

#### SC-SSE-008（high）：detectors 数组包含后置审计完整结果

- **Given**: `PostAuditRunner.run()` 对完整累积内容执行深检并产生 `detector_results`
- **When**: 该结果被写入流式输出审计条目
- **Then**: 审计条目的 `detectors` 数组 **SHALL** 包含后置审计的完整检测器结果（name/action/confidence/risk_level）
- **And**:
  - `detectors` **SHALL** 不再恒为空数组
  - `post_audit` 字典 **SHALL** 保留 `effective_action` / `original_action` / `risk_level` 等既有字段

#### SC-SSE-009（high）：window_count 以实际值填充

- **Given**: handler 在 `process_chunk` 循环中逐窗口执行检测
- **When**: 每次消费并检测一个完整窗口
- **Then**: handler **SHALL** 累加窗口计数，并在审计时以实际值填充 `window_count`（不再恒为占位 0）
- **And**:
  - `window_count` **SHALL** 等于本次流式会话实际检测的窗口总数
  - `window_count` 仅对流式（streaming=True）条目有效，非流式条目不受影响

---

### REQ-SSE-004 — PostAuditRunner 与 handler 透传 `request_id` 与输入侧 `language`（B-07 / DESIGN 6.6）

#### SC-SSE-010（high）：PostAuditRunner 透传 request_id

- **Given**: 后置审计被触发，当前请求持有非空 request_id
- **When**: 调用 `PostAuditRunner.run(content, request_id=..., language=...)`
- **Then**: PostAuditRunner **SHALL** 接收并在构建 DetectionContext 时透传 request_id，不再硬编码空字符串
- **And**:
  - 后置审计生成的 `DetectionContext.request_id` **SHALL** 等于当前请求 request_id

#### SC-SSE-011（high）：handler 复用输入侧 language

- **Given**: 输入侧已检测出 language（如 `detect_language_for_messages` 的返回）
- **When**: handler 为滑动窗口与后置审计构建 DetectionContext
- **Then**: handler **SHALL** 接收输入侧 language 并写入 `DetectionContext.language`
- **And**:
  - 滑动窗口与后置审计 **SHALL** 复用输入侧语言，不重新检测

#### SC-SSE-012（medium）：流式输出审计 language 采用输入侧

- **Given**: 流式输出审计条目构建时存在输入侧 language
- **When**: 写入 AuditEntry
- **Then**: 流式输出审计条目的 `language` **SHALL** 采用输入侧 language
- **And**:
  - 当输入侧未检测出语言时，`language` **SHALL** 保持 None，不产生伪值

---

### REQ-SSE-005 — 修正不引入回归（B-03/B-05/B-06/B-07 / Decision 14/15）

#### SC-SSE-013（high）：无输出检测器时透明透传不回归

- **Given**: 未配置输出检测器（has_detection=False）
- **When**: 发起流式请求
- **Then**: 网关 **SHALL** 保持透明透传，逐 chunk 转发并在末尾发出 `[DONE]`
- **And**:
  - 该路径 **SHALL** 不执行 SSEBuffer 重组、滑动窗口或后置审计，行为与修正前一致

#### SC-SSE-014（medium）：buffer 模式行为与审计不回归

- **Given**: `streaming_config.mode == buffer` 且配置了输出检测器
- **When**: 缓冲模式完成全量检测并回放 buffered chunk
- **Then**: 缓冲模式 **SHALL** 保持既有行为（全量检测后 block 或回放 + `[DONE]`），且其审计仍使用该模式结果
- **And**:
  - `window_count` 与 SSEBuffer 重组 **SHALL** 仅作用于滑动窗口模式，不影响 buffer 模式

#### SC-SSE-015（medium）：ProviderError 错误路径不回归

- **Given**: provider 在流中抛出 ProviderError
- **When**: 滑动窗口模式捕获异常并发出 error 事件 + `[DONE]`
- **Then**: 错误路径 **SHALL** 仍输出事件序列 error + `[DONE]`，并照常记录审计条目
- **And**:
  - 错误路径审计的 `final_action` / `final_risk_level` **SHALL** 反映实际，不因修正写入虚假 block
  - 审计条目的 `detector_results` 与 `window_count` **SHALL** 以实际处理结果为准，缺失时保持空/None 而非伪造

---

## 3. 验证检查点

| CP | Scenario | 描述 |
|----|----------|------|
| CP-1 | SC-SSE-001 | SSEBuffer 跨 chunk 重组拆分事件 |
| CP-2 | SC-SSE-002 | 单 chunk 多事件按 `\n\n` 切分 |
| CP-3 | SC-SSE-003 | 末尾残留 flush 不丢内容 |
| CP-4 | SC-SSE-004 | 非 data 事件透传不受影响 |
| CP-5 | SC-SSE-005 | handler 单独维护输出侧 output_action/output_risk_level |
| CP-6 | SC-SSE-006 | 流中被阻断时审计记录 block 及 detector/category |
| CP-7 | SC-SSE-007 | 流式输出审计使用输出侧而非输入侧 |
| CP-8 | SC-SSE-008 | 后审计 detector_results 写入审计条目 |
| CP-9 | SC-SSE-009 | process_chunk 累加 window_count 并写入审计 |
| CP-10 | SC-SSE-010/011 | PostAuditRunner 透传 request_id 与 language |
| CP-11 | SC-SSE-012 | 流式输出审计 language 采用输入侧 |
| CP-12 | SC-SSE-013 | 无输出检测器时透明透传不回归 |
| CP-13 | SC-SSE-014 | buffer 模式行为与审计不回归 |
| CP-14 | SC-SSE-015 | ProviderError 错误路径不回归 |
| CP-15 | -- | sse-streaming 完整测试套件通过 |
| CP-16 | -- | lint 与类型检查通过 |
