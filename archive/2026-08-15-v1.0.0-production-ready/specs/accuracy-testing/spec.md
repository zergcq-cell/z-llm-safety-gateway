# accuracy-testing — 行为规格（Human View）

> 变更：2026-08-15-v1.0.0-production-ready | 置信度：high

## Requirements

### REQ-ACC-001: tests/accuracy/ 提供 4 个规则型内置检测器的固定样本集

**SC-ACC-001**（置信度 high）— evidence: proposal.yaml -> what_changes C4; design.md D3

- GIVEN: tests/accuracy/samples/ 目录
- WHEN: 检查样本集文件
- THEN: prompt_injection、pii_redaction、sensitive_words、secret_leak 四个检测器 SHALL 各有一个样本 YAML 文件
- AND: 每个样本文件 SHALL 含 positive 与 negative 两组样本，每组 ≥20 条
- AND: 样本 SHALL 离线可复现（无网络依赖、无外部数据源）
- AND: 样本 SHALL 有预期 action 标注（allow/block）以便断言

### REQ-ACC-002: accuracy 测试断言准确率阈值并可离线运行

**SC-ACC-002**（置信度 high）— evidence: proposal.yaml -> what_changes C4; design.md D3

- GIVEN: tests/accuracy/test_accuracy.py
- WHEN: 运行 accuracy 测试（pytest tests/accuracy）
- THEN: 每个规则型检测器的准确率（正负样本判对比例）SHALL ≥ 0.9
- AND: 误报率（negative 样本被判 block/flag 的比例）SHALL ≤ 0.1
- AND: toxicity（ML）检测器 SHALL 以 skipif 标注模型环境依赖，无模型时跳过而非失败
- AND: 测试 SHALL 不依赖网络与外部服务

### REQ-ACC-003: accuracy 测试集成到全量测试但不阻塞无模型环境

**SC-ACC-003**（置信度 medium）— evidence: proposal.yaml -> success_criteria 4

- GIVEN: 完整测试套件
- WHEN: 运行全量 pytest
- THEN: accuracy 测试 SHALL 正常执行（规则型全绿；toxicity 按环境 skip）
- AND: 规则型 accuracy 用例数 SHALL ≥ 4 个（每检测器 1 个）
- AND: 失败 SHALL 有明确错误信息（哪条样本判错）
