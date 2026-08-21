# v0.1.1 发布后加固设计调整

> 原始基线：Gate 2 已确认的 `design.md`、`specs/*` 与 `test-plan.md`
> 汇总日期：2026-08-21
> 结论：不改变网关公共 HTTP/检测器运行时契约；无需重新 Spec，Verify 修复已全部重建并复验

## 调整汇总

| ID | 调整 | 原因 | 状态 |
|----|------|------|------|
| ADJ-001 | 包元数据收紧为 Python `>=3.10,<3.13` | 与公开支持 3.10–3.12 完全一致 | 已接受 |
| ADJ-002 | Release 强制依赖可复用三版本 quality workflow | 防止 tag 从未验证提交直接公开发布 | 已接受 |
| ADJ-003 | 删除无语义的 `dry_run` 输入 | 手动触发已由 tag-only condition 保证永不发布 | 已接受 |
| ADJ-004 | 生产 Compose 使用可构建 sidecar、健康依赖、双副本端口和真实 readiness | 静态配置与 liveness 会掩盖安全能力缺席 | 已接受 |
| ADJ-005 | SDK/插件安装改用 GitHub Release wheel direct reference | v0.1.1 不发布 PyPI，必须提供真实渠道 | 已接受 |
| ADJ-006 | STDD 诊断覆盖率与 90% 发布硬门分离 | 对齐 Verify 规范且保持发布门槛 | 已接受 |
| ADJ-007 | 行为准则与漏洞披露使用不同入口 | 两类事件的隐私与处置流程不同 | 已接受 |
| ADJ-008 | 第 12 类作为独立 L3 锚定检查 | 上游 v2.9.5 正文只定义 a-k，且 vendored 内容不可改写 | 已接受 |

## 影响说明

- ADJ-001、002、004、005 在 Verify 中触发了新的 RED 契约或运行态失败；均已完成 GREEN、重构和全量回归。
- ADJ-004 的最终运行证据为：sidecar healthy；8080/8081 两个 gateway 副本均 healthy/ready；每个副本 configured=3、loaded=3、healthy=3、degraded=false；容器、网络、卷均已清理。
- ADJ-005 的 GitHub Release URL 在 Gate 3 后创建 `v0.1.1` Release 时变为可下载；远程发布前不会对外宣称已经可用。
- ADJ-008 不修改 `.stdd/skills/verify.md` 或 platform copies，以保持官方 v2.9.5 固定提交哈希；本报告单独记录 `(l) 锚定缺失` 的检查证据。

机器可读版本见 `design-adjustments.yaml`。
