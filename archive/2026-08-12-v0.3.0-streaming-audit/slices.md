# v0.3.0 切片执行计划

## Dependency Graph Summary

```
零依赖 ──────────────────────────────┐
                                     │
[Slice 1] config-system 扩展 (P0) ───┤
                                     ▼
[Slice 2] audit-logger (P0) ◄── 依赖 config audit 配置
[Slice 3] sse-streaming 核心 (P0) ◄── 依赖 config streaming 配置
[Slice 5] provider stream_forward (P0)  ◄── 零依赖（可并行）
                                     ▼
[Slice 4] post-audit-recall (P0) ◄── 依赖 Slice 3
                                     ▼
[Slice 6] fastapi-server 集成 (P0) ◄── 依赖 Slice 1/2/3/4/5
```

**并行化说明**：
- 并行组 1：Slice 1 + Slice 5（Slice 1 配置系统、Slice 5 provider，互不依赖）
- 并行组 2：Slice 2 + Slice 3（均依赖 Slice 1，彼此独立）
- 串行：Slice 4（依赖 Slice 3）→ Slice 6（依赖全部）

## Slice Execution Plan

| # | 优先级 | 风险 | 预估工时 | 并行组 | TC 覆盖 | 实现目标 | 依赖 |
|---|--------|------|---------|--------|---------|---------|------|
| 1 | P0 | 🟢 Low | M | 组1 | TC-CONF-001~009 | `config/models.py` + `config/validators.py` 新增 streaming/output_detection/audit/logging 配置 | 无 |
| 2 | P0 | 🟢 Low | M | 组2 | TC-AUD-001~013 | `audit/` 模块（logger/sanitizer/models）JSONL 双通道 | 1 |
| 3 | P0 | 🟡 Med | L | 组2 | TC-SSE-001~013 | `streaming/` 模块（sliding_window/sse/handler/memory） | 1 |
| 4 | P0 | 🟡 Med | M | — | TC-PAR-001~011 | `post_audit/` + `recall/` 模块 | 3 |
| 5 | P0 | 🟢 Low | S | 组1 | TC-FAST-001 | `providers/base.py` + `stream_forward()` 异步生成器 | 无 |
| 6 | P0 | 🟡 Med | L | — | TC-FAST-002~017 + 集成 | `routes/chat.py` + `app.py` 集成 stream=true 分支 + 审计 | 1,2,3,4,5 |

## Rationale

### Slice 1: config-system 扩展（P0，先行）
- **依赖关系**：零依赖。所有其他模块读取新配置，必须先行。
- **风险分析**：低风险，纯 Pydantic 模型新增。所有新字段有默认值，向后兼容 v0.2.0。
- **工作量估算**：M（9 个 TC，2 文件修改）。

### Slice 2: audit-logger（P0，可并行）
- **依赖关系**：依赖 Slice 1 的 AuditConfig/LoggingConfig。与 Slice 3 相互独立。
- **风险分析**：低风险。JSONL 写入 + 脱敏，用标准库 logging.handlers。
- **工作量估算**：M（13 个 TC，3 文件新增）。

### Slice 3: sse-streaming 核心（P0，可并行）
- **依赖关系**：依赖 Slice 1 的 StreamingConfig。与 Slice 2 独立。
- **风险分析**：中风险。滑动窗口时序 + 流式动作处理 + 内存管理，异步逻辑复杂。
- **工作量估算**：L（13 个 TC，4 文件新增）。

### Slice 4: post-audit-recall（P0）
- **依赖关系**：依赖 Slice 3（后审计针对流式累积响应）与 Slice 1（recall 配置）。
- **风险分析**：中风险。Webhook 重试/退避时序 + 异步后审计调度。
- **工作量估算**：M（11 个 TC，2 文件新增）。

### Slice 5: provider stream_forward（P0，可并行）
- **依赖关系**：零依赖。BaseProvider 新增方法，复用现有钩子。
- **风险分析**：低风险。httpx stream() 封装。
- **工作量估算**：S（1 个 TC，1 文件修改）。

### Slice 6: fastapi-server 集成（P0）
- **依赖关系**：依赖 Slice 1/2/3/4/5 全部完成。
- **风险分析**：中风险。请求流分支集成 + 审计集成，需全量回归。
- **工作量估算**：L（16 个 TC + 集成测试，2 文件修改）。
