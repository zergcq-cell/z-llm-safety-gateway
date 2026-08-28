# Phase Context — 2026-08-28-rate-limit-deterministic-concurrency

## Phase 1: UNDERSTAND（completed 2026-08-28T18:05:43+08:00）

### 需求边界

- 修复 Python 3.11 上 `TC-RL-005` 受真实执行时间影响的非确定性失败。
- 明确并分别验证原子消费、连续补充和 burst 容量上限。
- 保持限流公开配置、HTTP 契约和生产算法语义不变。
- 非目标包括 Redis 限流、策略调整、其他能力和 Roadmap 文档漂移。

### 模式与锚定

- 用户选择 thorough 模式并确认 Gate 1。
- 限流属于安全控制边界，最低锚定 L3，实际采用 L3。
- 锚点：原始 security-observability change、现有 rate-limiting 主规范、
  `TokenBucket` 实现、`TC-RL-005` 与 CI 三版本矩阵。

## Phase 2: SPEC（completed 2026-08-28T19:00:51+08:00）

### 锁定的技术决策

- `TokenBucket(rate, burst, *, clock=None)` 增加 keyword-only 内部时钟依赖；默认仍为
  `time.monotonic`，middleware 与公开配置不变。
- 测试使用冻结且只能显式推进的 FakeClock；冻结并发、精确补充、burst cap 分开验证。
- 单纯 `asyncio.gather()` 不能证明锁存在；新增“预先持锁，consume 等待”的白盒证据。
- 不接受放宽成功数、降低 rate、全局 monkeypatch 或修改生产补充算法。
- 多版本环境缺失必须显式报告，不得计为通过。

### Project Principle Check

1. **Plugin / Flow**：不新增能力或 Flow 策略，只增加核心运行机制的可测试内部边界。
2. **显式策略 / 失败**：原子消费、合法补充、容量上限和环境缺失分别形成显式契约。
3. **透明边界 / 稳定契约**：两参数构造、配置、HTTP 429 和 `Retry-After` 均保持兼容。
4. **证据 / 数据保护**：使用确定性测试和三版本回归提供证据，不采集请求数据。

**原则取舍或偏离**：无。

### 经验库交叉检查

- `EXP-2026-0011`、`EXP-2026-0014`：避免把不可比较环境和真实时间噪声当作产品失败。
- `EXP-2026-0006`、`EXP-2026-0022`：checkpoint 使用真实测试路径、精确节点和唯一 TC-ID。

### 自动审查

- 发现并修复 3 项：冻结/推进行为混合、gather 无法直接证明锁、历史 agent spec 路径失效。
- 需求覆盖、Scenario 完备性、TC-ID 一致性、文档一致性全部通过；未解决项 0。
- L3 锚定自由度检查通过：关键时间边界、锁证据、兼容边界和多版本证据均已锁定。

### 产出物与覆盖

- `design.md`
- `canonical/specs/code/rate-limiting.yaml`
- `canonical/specs/agent/rate-limiting.yaml`
- `specs/rate-limiting/spec.md`
- `test-plan.md`
- 3 requirements / 6 scenarios / 6 test cases
- confidence：high 6 / medium 0 / low 0
- priority：P0 5 / P1 1 / P2 0

### 下一步

Gate 2 已确认。用户于 2026-08-28T19:18:31+08:00 回复“确认全部”，Phase 3～5
启用 `full_auto` 长程模式；同一问题连续修复 3 次失败、安全问题或通过率低于 95%
时降级，Gate 3 始终强制等待。

## Phase 3: SLICE（completed 2026-08-28T19:18:31+08:00）

### 切片结果

- Canonical dependency graph：1 node / 0 edge / 1 zero-dependency / 0 cycle。
- 共 3 个串行切片：S1 可控时钟（4 TC）→ S2 锁证据（1 TC）→ S3 多版本质量门（1 TC）。
- 3/3 Requirements、6/6 Scenarios、6/6 TC 被精确覆盖且每个 TC 只属于一个切片。
- 虽然 capability 零依赖，S1/S2 共享生产与测试文件，为保持严格 TDD 和避免写入冲突不并行。

### Phase 4 强制约束

- 每个行为切片严格 RED → GREEN → REFACTOR，并记录真实失败与通过证据。
- 不改变公开限流配置、HTTP 契约或连续补充算法。
- S3 使用真实 Python 环境，缺失或失效解释器不能计为通过。

## Phase 4: BUILD（completed 2026-08-28T19:30:38+08:00）

### S1 可控时钟与补充契约（completed 2026-08-28T19:22:46+08:00）

- **RED**：4 个目标节点中 3 个因旧构造函数拒绝 `clock` 而失败；默认两参数兼容测试在旧实现上已通过。
- **GREEN**：`TokenBucket` 增加 keyword-only `clock: Callable[[], float] | None`，默认仍在实例化时选择 `time.monotonic`；初始化与 refill 共用实例时钟。
- **REFACTOR**：FakeClock 只显式推进；冻结并发、精确补充、burst cap 和默认兼容分别测试。
- **切片验证**：TC 4/4；目标 4 passed；rate-limit 文件 10 passed；Ruff/Mypy/diff-check passed。
- **回归注记**：全量 1070 passed / 1 skipped；既有 `TC-PE-003` 宿主机吞吐门为唯一失败，隔离复跑仍约 1.65k req/s，且本 change 不修改其调用路径。通过率 >99.9%，不触发长程降级；Phase 5 将作为已知环境证据复核。

### S2 锁等待与原子消费证据（completed 2026-08-28T19:24:17+08:00）

- **RED 例外**：TC-RL-007 是对已存在 `asyncio.Lock` 行为新增的证明，首次执行即通过；按 Build Skill 的“已有等价行为”规则记录为 direct GREEN，不制造产品失败。
- **GREEN/REFACTOR**：持锁后让出事件循环，任务保持 pending 且 token 不变；释放后消费成功。无需修改生产锁实现，锁内仍无 I/O。
- **切片验证**：TC 1/1；目标 1 passed；rate-limit 文件 10 passed；Ruff/Mypy/diff-check passed。
- **回归证据**：排除已隔离证明无关的宿主机吞吐节点后，1070 passed / 1 skipped / 1 deselected。

### S3 多版本与完整质量门（completed 2026-08-28T19:30:38+08:00）

- **定向重复**：真实 uv 隔离环境 Python 3.10.21、3.11.16、3.12.14 各重复 3 次 rate-limit 文件；每版 30/30 passed。
- **CI 等价完整矩阵**：三版本均运行主 tests + 两个示例插件测试集及 90% coverage gate；每版均 1077 passed / 1 skipped。
- **覆盖率**：Python 3.10 93.34%，3.11 92.47%，3.12 93.34%。
- **静态质量**：Ruff 全范围 passed；Mypy 99 source files / 0 issues；`git diff --check` passed。
- **Traceability**：5 个本地 pytest checkpoint 节点真实可收集；STDD validate passed；Canonical verify 2/2。
- **环境结论**：三套解释器和隔离依赖均真实可用，无缺失环境；原 Python 3.11 时序失败已稳定消失。

## Phase 5: VERIFY（completed / Gate 3 pending 2026-08-28T19:47:54+08:00）

- **三路评审**：2 轮 × 3 代理全部完成；最终 C0/H0/M2/L0。两个 M 是既存 STDD async trace parser 和 `python` 别名可移植性限制。
- **评审修复**：程序化矩阵 checkpoint 改为可执行 shell；默认时钟测试移除共享 monkeypatch；proposal Human View、verify 状态、5+1 traceability 和结构证据已恢复一致。
- **最终质量矩阵**：当前最终 diff 上 Python 3.10/3.11/3.12 均 1077 passed / 1 skipped；覆盖率 93.34% / 92.47% / 93.34%；Ruff passed；Mypy 99 files / 0 issues。
- **TC/L3**：3 Requirements / 6 Scenarios / 6 TC 全覆盖；5 个 pytest 节点 + 1 个程序化矩阵；全部锚点存在，L3 passed。
- **失败模式**：a～l 12/12 完成，SKIPPED 0，产品未解决项 0。新增 EXP-2026-0023、0024，复用 4 条经验，总计 24 条。
- **设计调整**：0；无需 re-spec 或 re-build。
- **原则复核**：四项全部通过，无取舍或偏离；未新增数据采集。
- **已知后续**：内部 `consume(amount <= 0)` 既存输入缺口、STDD async trace parser、Python CLI 别名应分别进入后续 change，不在本 change 扩范围。
- **当前状态**：Gate 3 强制等待用户确认；确认前不进入 Phase 6、不提交、不推送。

## Phase 6: DELIVER（completed 2026-08-28T22:50:01+08:00）

- 用户于 2026-08-28T22:44:33+08:00 确认 Gate 3。
- change 已归档到 `archive/2026-08-28-rate-limit-deterministic-concurrency/`。
- Canonical proposal、rate-limiting code delta、agent checkpoint 和主索引已合并；临时恢复 active 路径执行 Canonical verify 2/2 后无条件移回归档。
- 累积主规范现为 REQ-RL-001～008、SC-RL-001～012；Human View 已创建并保留 merge 标记。
- `stdd structure merge` 已完成；本 change 新增经验仍为 discovered，无 deposited 条目可上传。
- 四项原则交付复核通过：核心职责未扩张、失败证据显式、公开契约稳定、无新增敏感数据。
- 定向交付复核：rate-limit 10 passed；Ruff passed；Mypy passed；主规范 YAML/Human/Canonical 结构一致。
- 用户已确认 Git 交付；批准 commit message `fix(rate-limit): make concurrency tests deterministic`、tag `rate-limit-determinism-2026-08-28` 及推送 origin。
