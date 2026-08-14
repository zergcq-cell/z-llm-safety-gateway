# rate-limiting - 行为规格（Human View）

> **Change**: 2026-08-12-v0.4.0-security-observability
> **Capability**: rate-limiting
> **Created**: 2026-08-12T16:00:00+08:00
> **Confidence**: high

## Description

限流能力：`TokenBucket` 维护 per `api_key` 或 per `ip` 的令牌桶，`rate`（每秒补充）与 `burst`（桶容量）控制流量。超限返回 429 + `Retry-After` 头 + OpenAI 兼容错误体。`storage: memory`（MVP）实现线程/事件循环安全，Redis 留待 v1.1+。

---

## Requirements

### REQ-RL-001: TokenBucket 维护 per api_key/ip 桶

**Description**: TokenBucket 按 `per` 维度（`api_key` 或 `ip`）维护令牌桶，`rate` 每秒补充令牌，`burst` 为桶容量。

**Confidence**: high

#### SC-RL-001: 桶内有余量时请求放行并消耗令牌

- **Given**: `security.rate_limit` 配置 `rate=10`、`burst=20`、`per=api_key`，某 api_key 桶内仍有令牌
- **When**: 该 api_key 发起的请求到达
- **Then**: RateLimitMiddleware **SHALL** 放行该请求并消耗一个令牌

#### SC-RL-002: 令牌耗尽后请求返回 429

- **Given**: 某 api_key 的桶令牌已耗尽（持续超速）
- **When**: 该 api_key 的后续请求到达
- **Then**: RateLimitMiddleware **SHALL** 拒绝该请求并返回 429

---

### REQ-RL-002: 从 security.rate_limit 读取 rate/burst/per/storage 配置

**Description**: 限流器从 `security.rate_limit` 读取 `rate`、`burst`、`per`、`storage` 配置。

**Confidence**: high

#### SC-RL-003: 配置被正确解析并初始化限流器

- **Given**: `security.rate_limit={rate:10, burst:20, per:api_key, storage:memory}`
- **When**: 网关加载配置并初始化限流器
- **Then**: 限流器 **SHALL** 使用 `rate=10`、`burst=20`、`per=api_key`、`storage=memory`
- **And**:
  - `per` **SHALL** 支持 'api_key' 与 'ip' 两个取值
  - `storage` **SHALL** 支持 'memory'（MVP，Redis 留待 v1.1+）

---

### REQ-RL-003: 超限返回 429 + Retry-After 头 + OpenAI 兼容错误体

**Description**: 超限时返回 HTTP 429，携带 `Retry-After` 头，错误体为 OpenAI 兼容格式。

**Confidence**: high

#### SC-RL-004: 超限响应包含 429、Retry-After 与兼容错误体

- **Given**: 请求被判定超限
- **When**: RateLimitMiddleware 生成拒绝响应
- **Then**: 响应 **SHALL** 返回 HTTP 429
- **And**:
  - 响应 **SHALL** 携带 Retry-After 头（建议重试秒数）
  - 错误体 **SHALL** 为 OpenAI 兼容格式

---

### REQ-RL-004: storage=memory 实现线程/事件循环安全

**Description**: 内存存储的令牌消耗为原子操作（asyncio.Lock 或等价机制），保证并发安全。

**Confidence**: high

#### SC-RL-005: 并发消耗令牌为原子操作

- **Given**: 多个请求并发命中同一 api_key 的桶
- **When**: 限流器并发读写令牌桶
- **Then**: 令牌消耗 **SHALL** 为原子操作（asyncio.Lock 或等价机制）
- **And**:
  - 并发下 **SHALL NOT** 出现令牌被超额消耗或出现负值

---

### REQ-RL-005: per=ip 时按客户端 IP 维度限流

**Description**: 当 `per=ip` 时，按客户端 IP 维度维护独立的令牌桶进行限流。

**Confidence**: high

#### SC-RL-006: 按 IP 维度判定超限并返回 429

- **Given**: `security.rate_limit per=ip`，某 IP 已超限
- **When**: 该 IP 的后续请求到达
- **Then**: RateLimitMiddleware **SHALL** 按 IP 维度判定超限并返回 429

---

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-RL-001 | 桶内有余量时请求放行并消耗令牌 |
| CP-2 | SC-RL-002 | 令牌耗尽后请求返回 429 |
| CP-3 | SC-RL-003 | rate/burst/per/storage 配置正确解析 |
| CP-4 | SC-RL-004 | 429 响应携带 Retry-After 与 OpenAI 兼容错误体 |
| CP-5 | SC-RL-005 | 并发令牌消耗为原子操作 |
| CP-6 | SC-RL-006 | per=ip 按客户端 IP 维度限流 |
| CP-7 | -- | ruff lint 通过 |
| CP-8 | -- | mypy 类型检查通过 |
