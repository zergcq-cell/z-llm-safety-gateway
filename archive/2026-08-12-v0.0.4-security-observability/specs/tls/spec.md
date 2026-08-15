# tls — 行为规格（Human View）

> **变更**: 2026-08-12-v0.4.0-security-observability
> **Capability**: tls
> **创建时间**: 2026-08-12T16:00:00+08:00
> **置信度**: high

## 描述

提供可选的**原生 TLS 终止**能力。通过 `security.tls.enabled/cert_file/key_file` 配置，在 `__main__.py` 中以 `uvicorn.run(..., ssl_certfile=..., ssl_keyfile=...)` 启动 HTTPS。**默认关闭**；生产环境建议由反向代理（Nginx/ALB）承担 TLS，但原生支持可满足直接暴露场景。

> 设计依据：design Decision 3；DESIGN 11.2 / 13.2。

---

## Requirements

### REQ-TLS-001：TLS 默认关闭，未配置时以 HTTP 启动

**描述**：未启用 `security.tls.enabled` 时，网关以明文 HTTP 启动，不产生 TLS 相关错误。

**置信度**: high

#### SC-TLS-001：TLS 未启用时以 HTTP 启动

- **Given**: 一份未设置 `security.tls.enabled`（或显式 `enabled: false`）的配置
- **When**: 网关通过 `__main__.py` 启动（`uvicorn.run`）
- **Then**: uvicorn 启动参数 **SHALL** 不包含 `ssl_certfile`/`ssl_keyfile`，网关以明文 HTTP 对外提供
- **And**:
  - 缺少 `security.tls` 配置时 **SHALL** 不产生任何 TLS 相关启动错误
  - 网关 HTTP 端点 **SHALL** 在配置的 host:port 上正常响应

---

### REQ-TLS-002：启用 TLS 时传递证书给 uvicorn 以支持 HTTPS

**描述**：启用后，将 `cert_file`/`key_file` 传给 `uvicorn.run`，网关通过 HTTPS 提供访问。

**置信度**: high

#### SC-TLS-002：启用 TLS 时通过 HTTPS 提供服务

- **Given**: 配置 `security.tls.enabled=true` 且提供有效的 `cert_file` 与 `key_file` 路径
- **When**: 网关通过 `__main__.py` 启动（`uvicorn.run`）
- **Then**: `uvicorn.run` **SHALL** 接收 `ssl_certfile=<cert_file>` 与 `ssl_keyfile=<key_file>`
- **And**:
  - 网关 **SHALL** 通过 HTTPS 对外提供服务，使用所配置证书完成 TLS 握手
  - 通过 `https://<host>:<port>` 的请求 **SHALL** 被成功受理并正常处理

---

### REQ-TLS-003：证书/私钥缺失或不可读时拒绝启动

**描述**：启用 TLS 但 `cert_file`/`key_file` 缺失时，启动失败并给出明确错误，**不得**静默降级为明文 HTTP。

**置信度**: medium

#### SC-TLS-003：证书文件缺失时拒绝启动

- **Given**: 配置 `security.tls.enabled=true`，但 `cert_file` 或 `key_file` 指向不存在的文件
- **When**: 网关通过 `__main__.py` 启动（`uvicorn.run`）
- **Then**: 启动过程 **SHALL** 失败并抛出明确错误，网关 **SHALL NOT** 以未加密 HTTP 静默降级运行
- **And**:
  - 错误信息 **SHALL** 指明缺失的证书/私钥文件路径
  - 操作员 **SHALL** 能在日志中定位 TLS 配置问题

---

## 验证检查点

| CP | Scenario | 描述 |
|----|----------|------|
| CP-1 | SC-TLS-001 | TLS 未启用时以 HTTP 启动 |
| CP-2 | SC-TLS-002 | TLS 启用时通过 HTTPS 提供服务 |
| CP-3 | SC-TLS-003 | 证书缺失时拒绝启动 |
| CP-4 | -- | tls 完整测试套件通过 |
| CP-5 | -- | lint 与类型检查通过 |
