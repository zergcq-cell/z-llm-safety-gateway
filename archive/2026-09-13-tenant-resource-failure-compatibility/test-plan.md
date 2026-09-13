# v0.3.0 租户资源、失败与兼容性隔离测试方案

## 1. 测试策略

采用单元、异步并发、真实 ASGI 集成和全量回归四层金字塔。测试优先验证租户资源边界、失败 reason code、取消释放、敏感数据投影和 legacy 协议兼容；复用前三项变更的身份、policy bundle、observation、Flow、Provider、SSE 与 post-audit 测试资产。

## 2. 测试案例

| ID | 场景 | 优先级 | 预期 |
|---|---|---:|---|
| TC-TRI-001 | 两租户不同并发预算并发执行 | P0 | 预算按租户隔离，互不阻断 |
| TC-TRI-002 | 成功/异常/超时/取消释放租约 | P0 | active lease 回到基线 |
| TC-TRI-003 | 队列和连接上限 | P0 | 稳定 `tenant_resource_exhausted` |
| TC-TFM-001 | 资源、超时、取消、初始化、Provider 失败矩阵 | P0 | 稳定分类，无跨租户 fallback |
| TC-TFM-002 | 失败观测脱敏与基数 | P0 | 最小归属，无原文/密钥/原始异常 |
| TC-TFM-003 | deadline 传播与重试上限 | P0 | 下游取消，重试有界 |
| TC-V03-001 | 四项变更聚合验收矩阵 | P0 | 全部 P0 契约通过 |
| TC-V03-002 | legacy HTTP/SSE/Provider 精确兼容 | P0 | 状态、body、headers、bytes 不变 |

## 3. 执行矩阵

| 领域 | 单元 | 并发/异步 | ASGI 集成 | 全量回归 |
|---|---|---|---|---|
| 资源隔离 | ResourceBudget、gate、lease | 跨租户屏障、取消 | sync/async/SSE | 是 |
| 失败矩阵 | 分类与映射 | deadline、Provider fault | HTTP/SSE/error body | 是 |
| 聚合兼容 | 文档/索引契约 | 端到端快照 | legacy 与多租户 | 是 |

## 4. 回归风险矩阵

| 区域 | 风险 | 等级 | 证据 |
|---|---|---:|---|
| middleware/app 装配 | 资源 gate 顺序错误 | 高 | 真实 create_app 链 |
| Flow runtime | 取消或 deadline 丢失 | 高 | 异步屏障与 fault injection |
| Provider/streaming | 长连接和重试泄漏 | 高 | SSE/Provider 集成 |
| post-audit | 后台快照脱离租户 | 中 | 任务生命周期测试 |
| legacy 路径 | 旧错误/协议变化 | 高 | 既有 corpus 全量回归 |
| observability | 失败标签高基数或泄密 | 高 | 对抗性日志/metric 断言 |

## 5. 建议顺序

P0：资源预算与租约、跨租户并发、失败矩阵、deadline/取消、legacy 兼容、聚合门。P1：公平性和压力边界。P2：非关键性能诊断。
