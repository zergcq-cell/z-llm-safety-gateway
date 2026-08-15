# graceful-shutdown — 行为规格（Human View）

> **变更**: 2026-08-12-v0.4.0-security-observability
> **Capability**: graceful-shutdown
> **创建时间**: 2026-08-12T16:00:00+08:00
> **置信度**: high

## 描述

提供**优雅停机**能力。通过 `server.stop_timeout`（默认 30s）配置，`__main__.py` 使用 `uvicorn.run`（由 uvicorn 内建 graceful shutdown 处理）并注册 SIGTERM handler。确保 in-flight 请求完成、审计日志 flush。文档明确 `stop_timeout < Docker stop_grace_period`。

> 设计依据：design Decision 6；DESIGN 13.4 / 决策 37。

---

## Requirements

### REQ-GS-001：SIGTERM 触发优雅停机，in-flight 请求完成

**描述**：收到 SIGTERM 后停止接受新连接，等待 in-flight 请求完成（最多 stop_timeout）再退出。

**置信度**: high

#### SC-GS-001：SIGTERM 后 in-flight 请求完成

- **Given**: 网关正在运行且有 in-flight 请求尚未完成
- **When**: 收到 SIGTERM 信号
- **Then**: 网关 **SHALL** 停止接受新连接，并等待所有 in-flight 请求完成（最多 stop_timeout）
- **And**:
  - in-flight 请求 **SHALL** 被正常处理并返回完整响应
  - 优雅停机完成后 **SHALL** 以退出码 0 退出

---

### REQ-GS-002：stop_timeout 默认 30s，超时强制退出

**描述**：`server.stop_timeout` 默认 30s，超时未完成则强制退出，不无限等待。

**置信度**: high

#### SC-GS-002：stop_timeout 超时后强制退出

- **Given**: `server.stop_timeout` 未配置（使用默认 30s）或显式设为某值，且有 in-flight 请求超过该时长仍未完成
- **When**: 收到 SIGTERM 信号后等待超过 stop_timeout
- **Then**: 网关 **SHALL** 在 stop_timeout 到期后强制退出，不再无限等待
- **And**:
  - 超时强退行为 **SHALL** 与 `server.stop_timeout` 配置一致

---

### REQ-GS-003：停机时冲刷审计日志并释放资源

**描述**：优雅停机收尾阶段冲刷审计日志并释放检测器/提供方资源。

**置信度**: medium

#### SC-GS-003：停机时 flush 审计日志并释放资源

- **Given**: 网关收到 SIGTERM 且已等待 in-flight 请求完成
- **When**: 执行优雅停机收尾阶段
- **Then**: 网关 **SHALL** 冲刷审计日志，保证已生成条目持久化
- **And**:
  - 检测器/提供方等资源 **SHALL** 被正常释放（如关闭连接）
  - 文档 **SHALL** 明确 `server.stop_timeout` 应小于 Docker `stop_grace_period`（建议 +5s）

---

## 验证检查点

| CP | Scenario | 描述 |
|----|----------|------|
| CP-1 | SC-GS-001 | SIGTERM 触发优雅停机，in-flight 请求完成 |
| CP-2 | SC-GS-002 | stop_timeout 超时后强制退出 |
| CP-3 | SC-GS-003 | 停机时 flush 审计日志并释放资源 |
| CP-4 | -- | graceful-shutdown 完整测试套件通过 |
| CP-5 | -- | lint 与类型检查通过 |
