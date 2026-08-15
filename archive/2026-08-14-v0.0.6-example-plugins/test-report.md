# v0.5.1 测试报告（轻量）

> 变更：2026-08-14-v0.5.1-example-plugins
> 模式：lightweight（纯增量资产，无接口变更）
> 日期：2026-08-14

## 验证结果

| 检查项 | 结果 |
|--------|------|
| in-process 示例测试 | **3 passed**（allow/block/modify 三路径） |
| python-grpc 示例测试 | **2 passed**（完整生命周期 E2E：initialize→detect→health→shutdown；HealthCheck serving） |
| 网关加载验证（模拟 entry point） | **OK**：`acme_keyword` 被 `load_plugins` 发现注册 |
| 全量回归 | **796 passed, 1 skipped**（无回归） |
| ruff（含示例源码） | All checks passed |
| 一致性检查 | 文档中命令/字段与 v0.5.0 实现一致（zlg detectors、[grpc] extras、endpoint 校验、透传规则） |

## 交付物

| 资产 | 说明 | 验证状态 |
|------|------|----------|
| `examples/plugins/python-inprocess/` | SDK in-process 插件示例（keyword policy） | ✅ 测试通过 + 网关加载验证 |
| `examples/plugins/python-grpc/` | gRPC sidecar 示例（server + 生成 stubs + gen_proto.sh） | ✅ E2E 测试通过 |
| `examples/plugins/go-grpc/` | Go sidecar 参考源码（go.mod + main.go + gen_proto.sh） | ⚠️ 环境无 Go，未编译运行（README 标注） |
| `docs/plugin-development.md` | Detector 开发指南（两种模式 + SDK + 测试 + 发布） | ✅ |
| `docs/grpc-integration.md` | gRPC 对接指南（合约/生命周期/配置/TLS/超时/调试） | ✅ |
| `docs/commercial-plugin.md` | 商业插件指南（模式/许可/打包/认证/计量） | ✅ |

## 设计调整

| # | 描述 |
|---|------|
| ADJ-001 | 示例 sidecar `HealthCheck` 初始返回 `serving`（进程存活语义；网关在 Initialize 之前先 HealthCheck）。首个测试暴露了"未初始化→not_serving"与网关调用顺序的矛盾，按 DESIGN 7.3.3 语义修正示例。 |

## 失败模式检查（lightweight 摘要）

- 未处理边缘情况：示例覆盖 allow/block/modify 全 action 路径 ✅
- 示例与实现脱节风险：通过 E2E 测试（用网关 `GRPCDetector` 客户端驱动）与网关加载模拟控制 ✅
- 文档漂移风险：三份文档引用字段/命令均与 v0.5.0 实现核对 ✅
