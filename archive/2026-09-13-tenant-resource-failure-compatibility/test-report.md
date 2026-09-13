# v0.3.0 Change 4 测试报告（Gate 3 材料）

## 总体概况

- 聚焦 Change 4 测试：**275 passed, 1 skipped**
- 非网络全量回归：**1190 passed, 1 skipped**
- Ruff：通过
- mypy：通过（99 source files）
- `git diff --check`：通过
- 覆盖率：本轮以既有全仓覆盖率 93% 为诊断基线；新增资源模块由定向测试覆盖
- E2E：项目配置关闭，N/A

## TC 覆盖

| TC | 自动化证据 | 结果 |
|---|---|---|
| TC-TRI-001 | `tests/unit/tenancy/test_resources.py` | PASS |
| TC-TRI-002 | 取消与释放测试 | PASS |
| TC-TRI-003 | 队列上限测试 | PASS |
| TC-TFM-001 | `FailureOutcome` 稳定分类测试 | PASS |
| TC-TFM-002 | reason code 无秘密断言 | PASS |
| TC-TFM-003 | middleware deadline、流式生命周期与后台租约测试/检查 | PASS |
| TC-V03-001 | 文档、路线图和既有三项归档矩阵 | PASS |
| TC-V03-002 | legacy HTTP/SSE/Provider 回归 | PASS |

## 环境信号与未完成项

1. gRPC 集成测试在当前沙箱无法绑定 `127.0.0.1:0`，属于环境权限限制；既有 gRPC 代码未被 Change 4 修改。补完计划：在允许本地端口的 CI runner 执行同一测试矩阵。
2. 历史 `TC-PE-003` 非插桩吞吐基准受当前宿主调度影响；该测试不在本 change diff，功能与 P0 质量门不受影响。补完计划：在独占 CI runner 保留基准。

## 失败模式 a–l

- (a) 路径/API：PASS；新增模块、配置字段和错误代码均可解析。
- (b) 范围蔓延：PASS；改动限于资源运行机制、兼容文档和测试。
- (c) 级联错误：PASS；资源失败显式返回，不吞异常、不跨租户 fallback。
- (d) 上下文丢失：PASS；冻结 ResourceSnapshot 贯穿请求。
- (e) 工具误用：PASS；使用项目测试、Ruff、mypy 和 Git 检查。
- (f) 运行时偏差：PASS；聚焦异步并发、取消和释放测试通过。
- (g) 管线断链：PASS；middleware、streaming、Provider 生命周期链路已接线。
- (h) 内容质量：PASS；路线图和 CHANGELOG/AGENTS 状态一致。
- (i) 指令衰减：PASS；长程模式仍保留 Gate 3 强制确认。
- (j) 覆盖真空：PASS；三个 capability 均有自动化测试或既有回归资产。
- (k) 契约断层：PASS；`tenant_resource_exhausted`、`tenant_resource_timeout` 和 HTTP body 字段一致。
- (l) 锚定缺失：PASS；引用前三项租户变更及 legacy 测试资产。

## 设计调整

详见 [design-adjustments.md](design-adjustments.md)；不需要重新规格。

## 项目原则复核

四项原则均满足：资源隔离保持核心机制最小，失败策略显式，旧协议透明兼容，失败证据最小化且不含原文/密钥。

## 结论

Change 4 的五项目标已实现，质量门在当前环境可执行范围内通过。Gate 3 需用户确认后才进入 Phase 6 归档与交付。
