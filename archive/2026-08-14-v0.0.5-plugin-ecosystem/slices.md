# v0.5.0 切片执行计划

> 变更：2026-08-14-v0.5.0-plugin-ecosystem
> 模式：thorough / full_auto（长程）

## Dependency Graph Summary

```
detector-sdk ──┐ (零依赖, 并行组1)
               │
config-system ─┤ (零依赖, 并行组1)
               │
               ▼
detector-framework ◄── plugin-loader
       │  ▲                │
       │  └── grpc-sidecar │
       ▼                   │
plugin-cli ◄───────────────┘
       │
       ▼
fastapi-server (集成所有)
```

- 零依赖节点：`detector-sdk`、`config-system`（并行组 1）
- 依赖链：config-system → detector-framework → grpc-sidecar/plugin-loader → plugin-cli → fastapi-server
- 关键路径：config-system → detector-framework → grpc-sidecar → fastapi-server（最长链）

## Slice Execution Plan

| # | 切片 | Capabilities | TC | 工作量 | 风险 | parallel_group | Rationale |
|---|------|--------------|-----|--------|------|----------------|-----------|
| 1 | SDK 包骨架 | detector-sdk | SDK-001/002/006 | L | 🟢 | 1 | 零依赖；接口定义被插件/gRPC 参照 |
| 2 | 配置扩展 | config-system | CFG-501/502/503 | S | 🔴 | 1 | 零依赖；type=grpc 是下游前提 |
| 3 | 检测器框架扩展 | detector-framework | DF-501/503 | M | 🟢 | 2 | 依赖 Slice 2；registry 能力扩展 |
| 4 | 插件加载器 | plugin-loader | PL-001~004 | M | 🟡 | 2 | 依赖 Slice 3 |
| 5 | gRPC 合约与客户端 | grpc-sidecar | GRPC-001~008 | L | 🔴 | 2 | 依赖 Slice 2/3；最大独立切片 |
| 6 | CLI | plugin-cli + sdk cli | CLI-001~004, SDK-003/004/005 | M | 🟢 | 3 | 依赖 Slice 1/4/5 |
| 7 | FastAPI 集成 | fastapi-server + df | FSA-501~503, DF-502 | M | 🔴 | 3 | 依赖全部；收尾集成 |

## Rationale

- **Slice 1 先行**：SDK 包零依赖，且其接口定义（Detector/DetectionResult/DetectionContext）是第三方插件与 gRPC 客户端实现的契约基准，先锁定接口避免返工。
- **Slice 2 先行**：`type=grpc` 配置语义与校验是 gRPC sidecar 与 registry 创建路径的前提，且含启动报错规则（安全相关，高风险）。
- **Slice 3/4 并行**：registry 扩展（register_from_entry_points）与插件加载器紧耦合，但实现边界清晰（registry 提供能力、loader 调用能力），同组并行。
- **Slice 5 独立成片**：gRPC 客户端 8 个 TC、涉及 protobuf 生成代码、超时与 TLS，工作量大且风险高（外部协议），独立切片便于隔离验证。
- **Slice 6/7 收尾**：CLI 依赖 1/4/5 的成果；FastAPI 集成依赖全部切片，作为最终集成验证。
- **风险隔离**：Slice 2/5/7 标红（配置校验、外部协议、核心集成），每片完成即全量验证，防止问题累积。

## 验证策略

- 每个切片完成：该切片 TC 全绿 + ruff + mypy
- Slice 5 需 grpcio：验证环境 `pip install -e .[grpc]`（或已有）
- Slice 7 完成后：全量 pytest + coverage ≥ 80%
