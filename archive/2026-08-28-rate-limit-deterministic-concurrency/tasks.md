# 令牌桶确定性并发任务清单

## 1. 可控单调时钟边界（P0）

- [x] 1.1 RED：重写 TC-RL-005，冻结时间下 50 次并发消费恰好成功 burst 次。
- [x] 1.2 RED：新增 TC-RL-008，验证未推进时不补充、推进后精确补充 `rate × elapsed`。
- [x] 1.3 RED：新增 TC-RL-009，验证补充不超过 burst。
- [x] 1.4 RED：新增 TC-RL-010，验证两参数构造和默认生产时钟兼容。
- [x] 1.5 GREEN：以最小实现为 `TokenBucket` 增加 keyword-only 可注入时钟。
- [x] 1.6 REFACTOR：收敛 FakeClock 与测试命名，运行定向及受影响 middleware 回归。

## 2. 并发序列化证据（P0）

- [x] 2.1 RED：新增 TC-RL-007，先持锁并证明 `consume()` 在释放前等待且不修改 token。（依赖 #1.5）
- [x] 2.2 GREEN：确认现有 `asyncio.Lock` 满足测试；若失败，仅做保持设计契约的最小修复。
- [x] 2.3 REFACTOR：检查锁内无 I/O、失败消费不扣减、token 不为负，并运行全部 rate-limit 测试。

## 3. 多版本与完整质量门（P1）

- [x] 3.1 执行 TC-RL-011：在 Python 3.10、3.11、3.12 真实隔离环境重复 rate-limit 定向测试。
- [x] 3.2 运行完整 pytest 与项目覆盖率门。
- [x] 3.3 运行 Ruff、Mypy、`git diff --check` 和 STDD traceability 检查。
- [x] 3.4 缺失或失效环境显式记录，不得标记为通过。
