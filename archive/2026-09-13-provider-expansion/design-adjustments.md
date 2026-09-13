# Design Adjustments

- **ADJ-001**：ProviderConfig 增加 `anthropic` 和 `gemini` 类型，保持既有字符串契约；无需重新规格设计。
- **ADJ-002**：`/v1/models` 使用 Provider 对应认证头，避免将 OpenAI Bearer 语义错误应用到新 Provider。
