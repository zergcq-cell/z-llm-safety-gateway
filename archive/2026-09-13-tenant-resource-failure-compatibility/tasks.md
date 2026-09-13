# Change 4 实现任务

## S1 ResourceBudget 与租户闸门

- [x] 定义冻结 ResourceBudget 配置与上限校验（TRI-001）
- [x] 实现按租户分片的有界并发闸门和队列（TRI-001, TRI-003）
- [x] RED→GREEN→REFACTOR 聚焦测试

## S2 租约生命周期

- [x] 实现成功、异常、超时、取消的 finally 释放（TRI-002）
- [x] 增加 active count、队列归零和取消注入测试

## S3 失败矩阵与 deadline

- [x] 定义 FailureOutcome、稳定 reason code 和 HTTP/SSE 映射（TFM-001）
- [x] 传播 deadline、限制重试并接入最小观测（TFM-002, TFM-003）
- [x] 完成失败模式测试

## S4 生产路径接线

- [x] 接入同步、异步、SSE、buffer、Provider 和 post-audit（TFM-003）
- [x] 验证同一租户快照、取消传播和跨租户无污染

## S5 聚合验收与兼容

- [x] 回归旧单租户 HTTP/SSE/Provider 协议（V03-002）
- [x] 执行四项 v0.3.0 聚合矩阵和隐私/资源门（V03-001）
- [x] 更新文档、canonical、索引和归档材料
