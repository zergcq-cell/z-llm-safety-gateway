# v0.3.0 测试方案与详细案例

> 版本：v0.3.0
> 创建日期：2026-08-12
> 对应 Phase 2 Spec：
> - `specs/sse-streaming/spec.yaml`（9 REQ / 21 SC）
> - `specs/post-audit-recall/spec.yaml`（10 REQ / 22 SC）
> - `specs/audit-logger/spec.yaml`（10 REQ / 15 SC）
> - `specs/config-system/spec.yaml`（5 REQ / 10 SC）
> - `specs/fastapi-server/spec.yaml`（7 REQ / 17 SC）

## 一、测试策略

### 1.1 测试金字塔

v0.3.0 以单元测试为主（流式窗口、SSE 事件、审计记录模型、配置校验），辅以集成测试（流式请求流、审计集成）。流式相关的异步逻辑使用 pytest-asyncio 和 mock 的 httpx 流式客户端。Webhook 召回使用 mock transport 避免真实网络调用。

### 1.2 测试原则

- 严格 TDD：RED（写失败测试）→ GREEN（最小实现）→ REFACTOR
- 流式检测逻辑与 SSE 转发逻辑分离，便于独立测试
- 审计日志写入异步化，测试中使用 await 等待或 mock 验证
- Webhook 召回通过注入 mock 的 httpx transport 测试重试/退避，不发起真实请求
- 所有新增配置字段测试向后兼容（旧配置无需修改）

### 1.3 已有测试资产

| 测试文件 | 用例数 | 类型 | 覆盖范围 |
|----------|--------|------|----------|
| tests/unit/pipeline/test_engine.py | ~15 | 单元 | Pipeline 并行执行、短路 |
| tests/unit/routes/test_chat_pipeline.py | ~6 | 单元 | 非流式 pipeline 集成 |
| tests/integration/test_pipeline_flow.py | ~4 | 集成 | 完整非流式请求流 |
| tests/unit/config/test_v2_models.py | ~11 | 单元 | config v2 模型 |
| tests/unit/config/test_v2_validators.py | ~13 | 单元 | config v2 校验 |

## 二、详细测试案例

### 功能 1：SSE 流式代理与滑动窗口（sse-streaming）

#### 案例 1.1 — stream=true StreamingResponse 转发

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-001 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | 配置 provider 返回 SSE chunks；请求 stream=true |
| **输入** | POST /v1/chat/completions with stream=true |
| **预期结果** | 返回 StreamingResponse，chunks 按序转发，data: [DONE] 结尾 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.2 — 输入 block 时不启动流式

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-002 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-002（及 fastapi-server SC-003） |
| **优先级** | P0 |
| **预置条件** | input detector block；请求 stream=true |
| **输入** | POST /v1/chat/completions with stream=true |
| **预期结果** | 返回 400 safety_block，无 SSE 流 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.3 — 滑动窗口字符级累积与滑窗

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-003 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-004（窗口累积） |
| **优先级** | P0 |
| **预置条件** | window_size=200, overlap=50 |
| **输入** | 累积 200+ 字符 |
| **预期结果** | 触发窗口检测，滑动 150 字符，保留 50 字符重叠 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.4 — 窗口 block 停止流式并发送 safety_block

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-004 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-005（及 fastapi-server SC-005） |
| **优先级** | P0 |
| **预置条件** | output detector 对某窗口返回 block |
| **输入** | 触发窗口检测 block |
| **预期结果** | 停止转发，发送 safety_block + [DONE] |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.5 — 窗口 flag 继续 + safety_flag 聚合

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-005 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-006（及 fastapi-server SC-006） |
| **优先级** | P1 |
| **预置条件** | send_flag_events=true；多检测器 flag 同一窗口 |
| **输入** | 触发窗口检测 flag |
| **预期结果** | 继续流式，每窗口一条 safety_flag，聚合最高 risk_level + 逗号分隔 flagged_by |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.6 — 窗口 modify 降级为 flag

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-006 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-007（及 fastapi-server SC-007） |
| **优先级** | P1 |
| **预置条件** | output detector 对窗口返回 modify |
| **输入** | 触发窗口检测 modify |
| **预期结果** | 降级为 flag，继续流式，审计记录 action: modify, applied: false |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.7 — buffer 模式缓冲 + 回放

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-007 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-008（及 fastapi-server SC-010） |
| **优先级** | P1 |
| **预置条件** | streaming.mode=buffer；安全响应 |
| **输入** | POST stream=true |
| **预期结果** | 缓冲完整响应后检测，安全则回放 chunks + [DONE] |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.8 — buffer 模式 block + 跳过 post-audit

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-008 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-009（及 fastapi-server SC-011, post-audit-recall SC-008） |
| **优先级** | P1 |
| **预置条件** | streaming.mode=buffer；检测 block |
| **输入** | POST stream=true |
| **预期结果** | 发 safety_block + [DONE] 无内容；post_audit.executed: false, reason: buffer_mode |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.9 — max_response_size block 策略

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-009 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-010（及 fastapi-server SC-008） |
| **优先级** | P0 |
| **预置条件** | on_max_size=block；响应超 1MB |
| **输入** | 累积超 max_response_size |
| **预期结果** | safety_block（blocked_by: streaming_limit, category: response_too_long, risk_level: medium, confidence: 1.0）+ [DONE] |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.10 — max_response_size truncate 策略

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-010 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-011（及 fastapi-server SC-009） |
| **优先级** | P1 |
| **预置条件** | on_max_size=truncate；响应超限 |
| **输入** | 累积超 max_response_size |
| **预期结果** | 停止累积但继续流式；post_audit_truncated: true |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.11 — 检测器并行 + block 短路

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-011 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-013 |
| **优先级** | P1 |
| **预置条件** | 多 output 检测器 |
| **输入** | 触发窗口检测 |
| **预期结果** | 并行执行，任一 block 短路 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.12 — SSE 事件格式

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-012 |
| **对应 Spec** | sse-streaming/spec.yaml → SC-014 |
| **优先级** | P0 |
| **预置条件** | 标准 + 自定义事件 |
| **输入** | 检查 SSE 输出格式 |
| **预期结果** | data: {chunk} / event: safety_block / event: safety_flag / data: [DONE] 格式正确 |
| **当前状态** | ❌ 测试缺 |

#### 案例 1.13 — 流式 Provider 错误事件

| 字段 | 内容 |
|------|------|
| **ID** | TC-SSE-013 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-002 |
| **优先级** | P1 |
| **预置条件** | 流式中 provider 错误 |
| **输入** | Provider 抛异常 |
| **预期结果** | 发送 SSE error 事件 + [DONE]，干净关闭 |
| **当前状态** | ❌ 测试缺 |

### 功能 2：后审计与召回（post-audit-recall）

#### 案例 2.1 — 流式完成后后台后审计

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-001 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-001（及 fastapi-server SC-012） |
| **优先级** | P0 |
| **预置条件** | 流式完成 + [DONE] 已发；post_audit 开启 |
| **输入** | 流式响应完成 |
| **预期结果** | 后台对完整响应深度检测，不阻塞客户端 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.2 — 后审计使用 output 检测器与一致阈值

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-002 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-002 |
| **优先级** | P1 |
| **预置条件** | output 检测器已配置 |
| **输入** | 执行后审计 |
| **预期结果** | 使用所有启用 output 检测器，阈值一致 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.3 — 后审计 modify 降级为 flag

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-003 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-003 |
| **优先级** | P1 |
| **预置条件** | 后审计检测 modify |
| **输入** | 后审计返回 modify |
| **预期结果** | 降级为 flag，审计记录 original_action: modify, effective_action: flag, applied: false |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.4 — 后审计 block 触发召回

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-004 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-004 |
| **优先级** | P0 |
| **预置条件** | 后审计发现 block 风险 |
| **输入** | 后审计返回 block |
| **预期结果** | 触发召回，审计记录 recalled: true, severity: critical |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.5 — SSE 召回事件格式

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-005 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-005 |
| **优先级** | P1 |
| **预置条件** | recall.method=sse；连接活跃 |
| **输入** | 后审计 block |
| **预期结果** | 发送 event: safety_recall, data 含 request_id/risk_level/reason/category |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.6 — SSE 召回连接断开丢失

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-006 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-005b |
| **优先级** | P2 |
| **预置条件** | recall.method=sse；客户端已断开 |
| **输入** | 后审计 block |
| **预期结果** | SSE 召回丢失（记录日志），后续请求不受影响 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.7 — Webhook 召回重试与退避

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-007 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-006 |
| **优先级** | P0 |
| **预置条件** | recall.method=webhook；webhook 首次失败 |
| **输入** | 后审计 block |
| **预期结果** | POST 到 webhook_url，5s 超时，3 次重试（1s/2s/4s），2xx 成功 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.8 — Webhook 全败记录 failed

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-008 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-006b |
| **优先级** | P1 |
| **预置条件** | webhook 连续失败 |
| **输入** | 3 次重试全失败 |
| **预期结果** | 审计记录 recall_delivery: failed，无进一步动作 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.9 — recall.method 配置校验

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-009 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-007 |
| **优先级** | P1 |
| **预置条件** | recall.method 配置 |
| **输入** | 配置 sse/webhook/both |
| **预期结果** | 正确解析；webhook/both 缺 webhook_url 时报错 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.10 — 非流式 async 立即返回 + Webhook 召回

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-010 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-009（及 fastapi-server SC-014） |
| **优先级** | P0 |
| **预置条件** | stream=false, output_detection.mode=async |
| **输入** | POST 非流式请求 |
| **预期结果** | 立即返回响应，后台检测，风险时 Webhook 召回 |
| **当前状态** | ❌ 测试缺 |

#### 案例 2.11 — async 双审计记录

| 字段 | 内容 |
|------|------|
| **ID** | TC-PAR-011 |
| **对应 Spec** | post-audit-recall/spec.yaml → SC-010（及 fastapi-server SC-015） |
| **优先级** | P1 |
| **预置条件** | async 输出检测 |
| **输入** | 发送 + 后台检测 |
| **预期结果** | initial（pending）+ completion（completed）两条记录，共享 request_id |
| **当前状态** | ❌ 测试缺 |

### 功能 3：审计日志（audit-logger）

#### 案例 3.1 — JSONL 每方向一条记录

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-001 |
| **对应 Spec** | audit-logger/spec.yaml → SC-001（及 fastapi-server SC-016） |
| **优先级** | P0 |
| **预置条件** | audit.enabled=true |
| **输入** | 完成一个请求 |
| **预期结果** | input + output 各一条记录，共享 request_id |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.2 — 审计记录字段完整性

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-002 |
| **对应 Spec** | audit-logger/spec.yaml → SC-002 |
| **优先级** | P0 |
| **预置条件** | audit.enabled=true |
| **输入** | 检查审计记录 |
| **预期结果** | 包含 request_id/timestamp/direction/model/provider/content_hash/language/final_action/final_risk_level/durations/streaming 等字段 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.3 — detectors 数组六字段

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-003 |
| **对应 Spec** | audit-logger/spec.yaml → SC-003 |
| **优先级** | P0 |
| **预置条件** | 检测器执行 |
| **输入** | 检查 detectors 数组 |
| **预期结果** | 每个检测器 name/action/confidence/risk_level/duration_ms/error |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.4 — 流式特定字段

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-004 |
| **对应 Spec** | audit-logger/spec.yaml → SC-004 |
| **优先级** | P1 |
| **预置条件** | 流式请求 |
| **输入** | 检查审计记录 |
| **预期结果** | streaming/window_count/post_audit/post_audit_truncated/recalled/recall_method |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.5 — content_hash 始终存储

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-005 |
| **对应 Spec** | audit-logger/spec.yaml → SC-005 |
| **优先级** | P0 |
| **预置条件** | 任意请求 |
| **输入** | 检查审计记录 |
| **预期结果** | content_hash (SHA-256) 始终存在 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.6 — store_content=false 仅存 hash

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-006 |
| **对应 Spec** | audit-logger/spec.yaml → SC-006a |
| **优先级** | P0 |
| **预置条件** | store_content=false（默认） |
| **输入** | 检查审计记录 |
| **预期结果** | 仅存 content_hash，无明文 content |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.7 — store_content=true 存明文

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-007 |
| **对应 Spec** | audit-logger/spec.yaml → SC-006b |
| **优先级** | P1 |
| **预置条件** | store_content=true |
| **输入** | 检查审计记录 |
| **预期结果** | 存储明文 content |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.8 — JSONL 文件每日轮换

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-008 |
| **对应 Spec** | audit-logger/spec.yaml → SC-007a |
| **优先级** | P1 |
| **预置条件** | file.enabled=true, path 可写 |
| **输入** | 写入审计记录 |
| **预期结果** | JSONL 文件写入，TimedRotatingFileHandler 每日轮换 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.9 — stdout 结构化输出

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-009 |
| **对应 Spec** | audit-logger/spec.yaml → SC-007b |
| **优先级** | P1 |
| **预置条件** | stdout=true |
| **输入** | 写入审计记录 |
| **预期结果** | stdout 输出结构化 JSON |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.10 — 日志脱敏开启

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-010 |
| **对应 Spec** | audit-logger/spec.yaml → SC-008a |
| **优先级** | P0 |
| **预置条件** | sanitize_logs=true（默认） |
| **输入** | 内容含 API Key/Authorization |
| **预期结果** | 审计记录中敏感信息被 redact |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.11 — 日志脱敏关闭

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-011 |
| **对应 Spec** | audit-logger/spec.yaml → SC-008b |
| **优先级** | P2 |
| **预置条件** | sanitize_logs=false |
| **输入** | 内容含敏感信息 |
| **预期结果** | 不脱敏 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.12 — 异步写入失败仅 warning

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-012 |
| **对应 Spec** | audit-logger/spec.yaml → SC-009b |
| **优先级** | P1 |
| **预置条件** | 日志文件不可写 |
| **输入** | 写入审计记录 |
| **预期结果** | 记录 warning，请求不受影响 |
| **当前状态** | ❌ 测试缺 |

#### 案例 3.13 — audit.enabled=false 不写日志

| 字段 | 内容 |
|------|------|
| **ID** | TC-AUD-013 |
| **对应 Spec** | audit-logger/spec.yaml → SC-010b（及 fastapi-server SC-017） |
| **优先级** | P0 |
| **预置条件** | audit.enabled=false |
| **输入** | 完成请求 |
| **预期结果** | 不写入审计日志 |
| **当前状态** | ❌ 测试缺 |

### 功能 4：配置系统扩展（config-system）

#### 案例 4.1 — streaming 配置块解析

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-001 |
| **对应 Spec** | config-system/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | 含 streaming 配置块 |
| **输入** | 验证配置 |
| **预期结果** | 正确解析 StreamingConfig 所有字段 + 默认值 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.2 — streaming.mode 非法值报错

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-002 |
| **对应 Spec** | config-system/spec.yaml → SC-002 |
| **优先级** | P0 |
| **预置条件** | streaming.mode=tokenizer |
| **输入** | 验证配置 |
| **预期结果** | 报错，阻止启动 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.3 — on_max_size 非法值报错

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-003 |
| **对应 Spec** | config-system/spec.yaml → SC-003 |
| **优先级** | P1 |
| **预置条件** | on_max_size=stop |
| **输入** | 验证配置 |
| **预期结果** | 报错，阻止启动 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.4 — output_detection 配置解析

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-004 |
| **对应 Spec** | config-system/spec.yaml → SC-004 |
| **优先级** | P0 |
| **预置条件** | 含 output_detection 配置块 |
| **输入** | 验证配置 |
| **预期结果** | 正确解析 OutputDetectionConfig |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.5 — async 模式缺 webhook_url 报错

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-005 |
| **对应 Spec** | config-system/spec.yaml → SC-005 |
| **优先级** | P0 |
| **预置条件** | mode=async, webhook_url 空 |
| **输入** | 验证配置 |
| **预期结果** | 报错，阻止启动 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.6 — output_detection.mode 非法值报错

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-006 |
| **对应 Spec** | config-system/spec.yaml → SC-006 |
| **优先级** | P1 |
| **预置条件** | mode=offline |
| **输入** | 验证配置 |
| **预期结果** | 报错，阻止启动 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.7 — AuditConfig 扩展解析

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-007 |
| **对应 Spec** | config-system/spec.yaml → SC-007 |
| **优先级** | P0 |
| **预置条件** | 含扩展 audit 配置 |
| **输入** | 验证配置 |
| **预期结果** | 正确解析 store_content/file/stdout + 默认值 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.8 — LoggingConfig 解析

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-008 |
| **对应 Spec** | config-system/spec.yaml → SC-009 |
| **优先级** | P1 |
| **预置条件** | 含 logging 配置 |
| **输入** | 验证配置 |
| **预期结果** | 正确解析 level/format + 默认值 |
| **当前状态** | ❌ 测试缺 |

#### 案例 4.9 — v0.2.0 配置向后兼容

| 字段 | 内容 |
|------|------|
| **ID** | TC-CONF-009 |
| **对应 Spec** | config-system/spec.yaml → SC-010 |
| **优先级** | P0 |
| **预置条件** | v0.2.0 旧配置（无 streaming/output_detection/logging） |
| **输入** | 验证配置 |
| **预期结果** | 加载成功，所有新字段用默认值，无警告 |
| **当前状态** | ❌ 测试缺 |

### 功能 5：Provider 流式转发（fastapi-server）

#### 案例 5.1 — stream_forward 异步生成器

| 字段 | 内容 |
|------|------|
| **ID** | TC-FAST-001 |
| **对应 Spec** | fastapi-server/spec.yaml → SC-001 |
| **优先级** | P0 |
| **预置条件** | 配置 provider |
| **输入** | 调用 stream_forward |
| **预期结果** | 逐 chunk yield Provider SSE 数据 |
| **当前状态** | ❌ 测试缺 |

## 三、测试执行矩阵

| 功能模块 | 单元测试 | 集成测试 | E2E | 状态 |
|----------|---------|----------|-----|------|
| SSE 流式代理 | ✅ | ✅ | ❌ | 🟡 |
| 滑动窗口检测 | ✅ | ✅ | ❌ | 🟡 |
| 流式内存管理 | ✅ | ✅ | ❌ | 🟡 |
| buffer 模式 | ✅ | ✅ | ❌ | 🟡 |
| 后审计检测 | ✅ | ✅ | ❌ | 🟡 |
| 响应召回（SSE/Webhook） | ✅ | ✅ | ❌ | 🟡 |
| 非流式 async 输出检测 | ✅ | ✅ | ❌ | 🟡 |
| 审计日志系统 | ✅ | ✅ | ❌ | 🟡 |
| 日志脱敏 | ✅ | ❌ | ❌ | 🟡 |
| 配置系统扩展 | ✅ | ❌ | ❌ | 🟢 |

## 四、回归风险矩阵

| 风险区域 | v0.3.0 改动 | 已有回归保护 | 风险等级 |
|----------|-------------|-------------|---------|
| routes/chat.py | 增加 stream=true 分支 + 审计集成 | 非流式 pipeline 测试 | 🟡 |
| config/models.py | 新增 streaming/output_detection/audit/logging 配置 | config v2 测试 | 🟢 |
| providers/base.py | 新增 stream_forward | 非流式 forward 测试 | 🟢 |
| app.py | 初始化 AuditLogger | 现有 app 测试 | 🟢 |
| pipeline/engine.py | 复用（无改动） | 现有 pipeline 测试 | 🟢 |

## 五、建议补充顺序

1. **第一优先**（部署前必补）：TC-SSE-001/002/004/009、TC-PAR-001/004/007/010、TC-AUD-001/002/003/005/006/010/013、TC-CONF-001/002/004/005/007/009、TC-FAST-001
2. **第二优先**（部署后尽快补）：TC-SSE-003/005/006/007/008/010/011/013、TC-PAR-002/003/005/008/009/011、TC-AUD-004/007/008/009/012、TC-CONF-003/006/008
3. **第三优先**（后续补）：TC-SSE-012、TC-PAR-006、TC-AUD-011
