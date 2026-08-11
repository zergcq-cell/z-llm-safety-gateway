# Phase Context — 2026-08-11-v0.1.0-framework-skeleton

<!--
  阶段交接摘要 — 每个 phase 结束时由 AI 撰写对应章节。
  新 session Agent 优先读取此文件以快速恢复上下文。
  每章节末尾附"完整上下文文件清单"，需要更多细节时回溯原文。
  
  ⚠️ 此文件由 AI 自动维护，人类不应手动编辑。
  冲突时以各 phase 的正式产出物为准。
---

## Phase 1: UNDERSTAND (completed 2026-08-11T00:00:00+08:00)

### 关键决策
- **需求边界确定**：Phase 1 仅搭建框架骨架（FastAPI server + Config + Provider proxy + Content extractor + Health + Request ID + Docker），不包含 Pipeline/Streaming/Auth/Audit（详见 proposal.md Constraints / NonGoals）
- **优先级判断**：所有 8 个变更项均为 P0，因为这是全新项目的基础骨架，缺一不可
- **模式选择**：用户选择 thorough 模式（复杂度评分 8 分），不降级为 standard

### 用户关注点
- 用户特别强调了 STDD 流程的严格遵循（对话中多次确认 Gate 门）
- 用户对经验库机制感兴趣（询问了经验库为 0 的含义和获取方式）

### 被否决的方向
- 降级为 standard 模式 — 原因：用户明确选择保持 thorough 模式

### 产出物清单
- proposal.md — Gate 1 已确认，confirmed_at: 2026-08-11T00:00:00+08:00
- proposal.yaml — Canonical YAML 格式

### 完整上下文文件清单
- proposal.md：需求背景、8 项变更、6 个 Capability、24 条 Success Criteria
- proposal.yaml：AI 消费的 Canonical 格式

---

## Phase 2: SPEC (completed 2026-08-11T08:30:00+08:00)

### 关键技术决策
- 决策 1: src layout — 理由：防止意外导入未安装包，支持后续扩展；排除：flat layout（导入混乱）
- 决策 2: App Factory 模式 — 理由：支持测试时传入不同配置；排除：模块级全局 app（无法替换配置）
- 决策 3: Pydantic v2 + YAML + env var 插值 — 理由：DESIGN.md 指定 YAML 配置 + Pydantic 验证；排除：pydantic-settings（不支持 YAML）
- 决策 4: httpx AsyncClient + glob 路由 — 理由：FastAPI 生态推荐，支持 HTTP/2；排除：aiohttp（API 不如 httpx），requests（同步阻塞）
- 决策 5: 独立内容提取器模块 — 理由：DESIGN.md Section 3.4 伪代码直接实现，纯函数便于 Phase 2 集成
- 决策 6: ASGI 中间件实现 Request ID — 理由：DESIGN.md Section 11.7 要求 UUID v4 + 消毒；排除：Depends 注入（不适合横切关注点）
- 决策 7: 健康端点 liveness/readiness 分离 — 理由：K8s 标准实践
- 决策 8: Docker multi-stage build — 理由：减小镜像体积；排除：完整镜像（过大）
- 决策 9: OpenAI 兼容错误格式 — 理由：DESIGN.md Section 4.4 定义完整错误码

### 经验触发记录
- 无（经验库为空，全新项目首次变更）

### 已知坑点 / 注意事项
- 环境变量插值在 Pydantic 验证前执行，未设置变量解析为空字符串（非崩溃）
- 内容提取器 Phase 1 不接入请求流程，Phase 2 时接入 Pipeline
- /v1/chat/completions Phase 1 直接转发（无安全检测），响应附带 X-Safety-Action: allow
- 客户端 X-Request-ID 需消毒（正则 ^[a-zA-Z0-9_-]{1,128}$），防止 log injection
- glob 路由 first match wins，启动时检测重叠规则并告警

### 未解决问题（待 Phase 5 验证）
- 无（设计审查 0 问题，所有 spec 置信度 高:67 / 中:6 / 低:0）

### 产出物清单
- design.md — Gate 2 已确认，9 个技术决策含备选方案分析
- specs/fastapi-server/spec.yaml — 6 REQ, 13 SC
- specs/config-system/spec.yaml — 8 REQ, 17 SC
- specs/provider-proxy/spec.yaml — 10 REQ, 12 SC
- specs/content-extractor/spec.yaml — 12 REQ, 12 SC
- specs/health-endpoints/spec.yaml — 7 REQ, 9 SC
- specs/request-id/spec.yaml — 8 REQ, 10 SC
- test-plan.md — 73 TC (P0:63, P1:10, P2:0)
- 总计：51 Requirements, 73 Scenarios, 73 TC

### 完整上下文文件清单
- design.md：架构决策（9 个 Decisions）、请求处理流程图、组件依赖图、风险表
- specs/<capability>/spec.yaml：GIVEN/WHEN/THEN 行为规格（Canonical YAML）
- specs/<capability>/agent_spec.yaml：验证检查点（CP 映射 Scenario）
- specs/<capability>/spec.md：Human View 行为规格
- test-plan.md：TC-ID 映射、测试金字塔策略、测试执行矩阵、回归风险矩阵、补充顺序

---

## Current: Phase 2 已完成，等待 Phase 3 启动

### 当前状态
- Phase 2 (SPEC) 已完成并通过 Gate 2 确认
- 所有文档已写入 changes/2026-08-11-v0.1.0-framework-skeleton/
- 等待用户选择 Phase 3-5 执行模式（长程/普通）

### 下一步
- 执行 Step 8：模式选择
- 进入 Phase 3: SLICE（切片规划）
