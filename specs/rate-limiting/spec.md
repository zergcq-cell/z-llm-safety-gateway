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
---

> Merged from `2026-08-28-rate-limit-deterministic-concurrency` on 2026-08-28.

## REQ-RL-006：确定性的单调时间边界与生产兼容

#### Scenario: SC-RL-007 — 冻结时间下并发消费只使用初始 burst

- **GIVEN** `TokenBucket` 使用冻结的可控单调时钟、`burst=5`，且 50 个协程共享该桶
- **WHEN** 50 个协程并发调用 `consume`
- **THEN** `TokenBucket` SHALL 恰好允许初始 burst 对应的 5 次消费
- **AND** token 数 SHALL 始终不小于 0，且测试 SHALL NOT 依赖 wall clock、主机速度或事件循环调度速度

#### Scenario: SC-RL-008 — 显式时间推进精确补充 token

- **GIVEN** `TokenBucket` 使用可控单调时钟，当前 token 已耗尽且 rate 已知
- **WHEN** 时钟显式前进给定 elapsed 后触发补充
- **THEN** `TokenBucket` SHALL 精确补充 `rate × elapsed` 个 token
- **AND** 未显式推进时钟时 SHALL NOT 产生额外 token

#### Scenario: SC-RL-009 — 补充不超过 burst

- **GIVEN** 经过时间足以补充超过 burst 的 token
- **WHEN** 时钟显式前进后触发补充
- **THEN** 可用 token SHALL 被限制为 burst 容量

#### Scenario: SC-RL-010 — 默认时钟保持构造兼容

- **GIVEN** 现有调用方仅以 rate 和 burst 构造 `TokenBucket`
- **WHEN** 未传入测试时钟并执行消费与补充
- **THEN** `TokenBucket` SHALL 默认使用生产单调时钟并保持现有构造调用兼容
- **AND** `RateLimitMiddleware` 的公开配置与构造路径 SHALL 保持不变

## REQ-RL-007：明确的并发序列化边界

#### Scenario: SC-RL-011 — 已持锁时 consume 必须等待

- **GIVEN** `TokenBucket` 的消费锁已被测试持有且桶内有 token
- **WHEN** 另一个任务调用 `consume`
- **THEN** `consume` 任务 SHALL 在锁释放前保持等待
- **AND** 锁释放前 token 数 SHALL 保持不变；释放后消费 SHALL 原子完成且 token 不为负

## REQ-RL-008：受支持 Python 版本的稳定证据

#### Scenario: SC-RL-012 — Python 3.10～3.12 重复回归

- **GIVEN** Python 3.10、3.11、3.12 的项目隔离环境与同一变更提交
- **WHEN** 重复执行 rate-limit 定向回归及完整 pytest、Ruff、Mypy 和覆盖率门
- **THEN** 三个 Python 版本的相关回归 SHALL 稳定通过且既有并发案例不再出现时序失败
- **AND** 缺失或失效的版本环境 SHALL 被显式报告而不得计为通过，且完整质量门 SHALL 保持项目既有通过标准

## Verification Checkpoints

| Checkpoint | Scenario | Test Case / Evidence |
|------------|----------|----------------------|
| CP-RL-007 | SC-RL-007 | TC-RL-005：冻结时钟并发消费 |
| CP-RL-008 | SC-RL-008 | TC-RL-008：精确 elapsed 补充 |
| CP-RL-009 | SC-RL-009 | TC-RL-009：burst cap |
| CP-RL-010 | SC-RL-010 | TC-RL-010：默认构造兼容 |
| CP-RL-011 | SC-RL-011 | TC-RL-007：持锁等待 |
| CP-RL-012 | SC-RL-012 | TC-RL-011：三版本质量矩阵 |
