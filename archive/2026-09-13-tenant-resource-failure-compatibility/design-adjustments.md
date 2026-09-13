# Design Adjustments — tenant-resource-failure-compatibility

- **ADJ-001**：队列计数按“等待并发槽位”的请求计算，首个可用槽位不会因 `queue_limit=0` 被拒绝。
- **ADJ-002**：资源配置位于 `GatewayConfig.tenant_resources`，保留 `TenancyConfig` 的 identity-only 契约。
- **ADJ-003**：gRPC 端口绑定和历史吞吐基准的宿主限制在测试报告中披露，不伪报为产品通过或失败。

以上调整不改变规格目标，不需要重新进入 Phase 2。
