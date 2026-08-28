# Code Structure Delta — 2026-08-28-rate-limit-deterministic-concurrency
> 生成时间: 2026-08-28T19:37:15.359138 | Git commit: aaf14c6
> 置信度: 0.70 (AI-generated — 以源代码为准)

## 变更文件

- `GATE1_APPROVED`
- `GATE2_APPROVED`

## Verify 手工复核补充

> `stdd structure delta` 当前只枚举 change 目录中的结构标记，未识别工作树里的 Python
> 修改；以下列表由 `git diff --name-only` 与实际符号检查补充，不替代生成器输出。

- `src/z_llm_safety_gateway/ratelimit/token_bucket.py`
  - `TokenBucket.__init__` 新增 keyword-only `clock` 依赖，默认保持 `time.monotonic`。
  - `_refill` 改用实例时钟；消费锁与公开方法不变。
- `tests/unit/middleware/test_rate_limit.py`
  - 新增 `_FakeClock`。
  - 重写 `test_concurrent_safety`，新增 4 个可收集的确定性检查点。
