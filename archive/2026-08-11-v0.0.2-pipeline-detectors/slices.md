# v0.2.0 切片执行计划

## Dependency Graph Summary

```
Group 1 (无依赖，可并行):
  config-system ──────────────────────────────┐
  detector-framework ──┐                      │
  circuit-breaker ─────┤                      │
                       │                      │
Group 2 (依赖 Group 1):│                      │
  pipeline-engine ◄────┘ (depends: detector-framework, circuit-breaker)
  language-detection ◄── (depends: detector-framework)
                       │
Group 3 (依赖 Group 1):│
  prompt-injection-detector ◄── (depends: detector-framework)
  pii-detector ◄────────────── (depends: detector-framework)
  sensitive-words-detector ◄── (depends: detector-framework)
  secret-leak-detector ◄────── (depends: detector-framework)
  toxicity-detector ◄───────── (depends: detector-framework)
                       │
Group 4 (依赖全部):    │
  fastapi-server ◄──── (depends: pipeline-engine, all detectors, config-system, language-detection)
```

## Slice Execution Plan

| Slice | Capability | Priority | Risk | Effort | Parallel Group | Depends On |
|-------|-----------|----------|------|--------|---------------|------------|
| 1 | config-system + detector-framework + circuit-breaker | P0 | 3-4 | L | 1 | — |
| 2 | pipeline-engine + language-detection | P0 | 3 | L | 2 | Slice 1 |
| 3 | prompt-injection + pii + sensitive-words + secret-leak | P1 | 2 | M | 3 | Slice 1 |
| 4 | toxicity-detector | P1 | 3 | L | 3 | Slice 1 |
| 5 | fastapi-server (集成) | P0 | 4 | L | 4 | Slice 1-4 |

## Rationale

### Slice 1: Foundation (P0)
- **config-system**: 配置结构重构是所有其他功能的基础，必须先完成。高风险（向后兼容）。
- **detector-framework**: Detector ABC + DetectionContext + DetectionResult 是所有检测器和 pipeline 的基础模型。
- **circuit-breaker**: 独立状态机，无外部依赖，可与上述并行开发。

### Slice 2: Pipeline Engine (P0)
- **pipeline-engine**: 依赖 detector-framework 的模型和 circuit-breaker。核心并行执行引擎。
- **language-detection**: 依赖 detector-framework 的 DetectionContext。轻量模块，与 pipeline 并行开发。

### Slice 3: Rule-based Detectors (P1)
- 4 个基于规则的检测器，仅依赖 detector-framework 的 Detector ABC。
- 可并行开发，互不依赖。
- 工作量中等，每个检测器 1 个实现文件 + 1 个测试文件。

### Slice 4: ML Detector (P1)
- **toxicity-detector**: 单独切片，因为涉及 ML 模型加载（transformers + torch），依赖较重。
- 懒加载和离线模式需要特殊处理。

### Slice 5: Integration (P0)
- **fastapi-server**: 依赖所有前置切片。修改 routes/chat.py 集成 pipeline。
- 高风险：修改核心请求路径，需要确保向后兼容。
- 包含 SafetyHeadersMiddleware 升级和 Block 错误响应。
