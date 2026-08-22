# Capability: stdd-toolchain-recovery

## ADDED Requirements

### REQ-STDD-001：可信且离线可运行的 STDD CLI

CLI SHALL 固定到官方 v2.9.5 提交，保留 MIT 许可证、provenance 和哈希；`--help/status` SHALL 离线成功。

### REQ-STDD-002：Canonical 与结构索引补录

系统 SHALL 在不改写 archive 的前提下完成 readiness change 的 canonical 校验和基于真实 Git diff 的幂等结构合并。

### REQ-STDD-003：经验生命周期

三个已发现模式 SHALL 可查询；不满足阈值时 SHALL NOT 被伪造为 deposited/shared。
