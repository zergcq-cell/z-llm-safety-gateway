# content-extractor - Behavioral Specification

> **Capability**: content-extractor
> **Change**: 2026-08-11-v0.1.0-framework-skeleton
> **Created**: 2026-08-11T00:00:00+08:00
> **Confidence**: high

## Description

Extracts detectable text content from OpenAI messages arrays for safety detection. Supports string content and multimodal content (extracting text parts, skipping image_url parts). Provides modify writeback functionality to apply detector modifications back to the original request, preserving image parts in multimodal messages. Implemented as an independent module in Phase 1; integrated into the Pipeline in Phase 2.

---

## Requirements

### REQ-001: Extract text from messages with role user, system, developer

**Confidence**: high

The `extract_content` function iterates over the messages array and extracts text from messages whose role is `user`, `system`, or `developer`. These roles represent potential input attack surfaces (user input, system prompts, developer instructions).

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-001 | high | Messages array containing messages with roles `user`, `system`, and `developer`, each with string content | `extract_content` is called on the messages array | Function SHALL return an ExtractedContent object for each user, system, and developer message |

---

### REQ-002: Skip messages with role assistant, function, tool

**Confidence**: high

Messages with role `assistant`, `function`, or `tool` are not extracted. These roles represent historical context, LLM-generated responses, or internal function/tool results that do not require input-side detection.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-002 | high | Messages array containing messages with roles `assistant`, `function`, and `tool` | `extract_content` is called on the messages array | Function SHALL NOT return any ExtractedContent objects for assistant, function, or tool messages |

---

### REQ-003: Handle string content directly

**Confidence**: high

When a message's `content` field is a string, the entire string is extracted as the text of the ExtractedContent.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-003 | high | A message with role `user` and content as a string `Hello world` | `extract_content` is called on the messages array | Function SHALL return an ExtractedContent with text equal to `Hello world` |

---

### REQ-004: Handle multimodal content - extract text parts, skip image_url parts

**Confidence**: high

When a message's `content` field is a list (multimodal), only parts with `type: "text"` are extracted. Parts with `type: "image_url"` and any other types are skipped.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-004 | high | A message with role `user` and content as a list: `[{'type': 'text', 'text': 'Describe this'}, {'type': 'image_url', 'image_url': {'url': '...'}}]` | `extract_content` is called on the messages array | Function SHALL return an ExtractedContent with text from the text part only. image_url parts SHALL be skipped. The extracted text SHALL be `Describe this`. |

---

### REQ-005: For multimodal, join text parts with newline

**Confidence**: high

When a multimodal message contains multiple text parts, the extracted texts are joined with a newline (`\n`) separator.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-005 | high | A message with role `user` and content as a list: `[{'type': 'text', 'text': 'Line 1'}, {'type': 'text', 'text': 'Line 2'}]` | `extract_content` is called on the messages array | Function SHALL return an ExtractedContent with text equal to `Line 1\nLine 2` |

---

### REQ-006: Each extracted message includes message_index and role in ExtractedContent

**Confidence**: high

The `message_index` field in ExtractedContent corresponds to the position of the message in the original messages array (not a sequential count of extracted items). The `role` field preserves the original message role.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-006 | high | Messages array with messages at indices 0 (system), 1 (user), 2 (assistant) | `extract_content` is called on the messages array | Each ExtractedContent SHALL include the original message_index from the messages array (0 and 1, not 2). Each ExtractedContent SHALL include the original role of the message. message_index SHALL be the position in the original messages array, not a sequential count of extracted items. |

---

### REQ-007: apply_modifications sorts modifications by priority (lower = first) before applying

**Confidence**: high

The `apply_modifications` function sorts the modifications list by `priority` in ascending order (lower number = higher priority = applied first) before applying them to the request.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-007 | high | A modifications list with priorities [20, 10, 100] targeting the same message | `apply_modifications` is called | Function SHALL sort modifications by priority ascending (10, 20, 100) before applying. Priority 10 SHALL be applied first. Priority 100 SHALL be applied last. |

---

### REQ-008: For string content, modification replaces the content directly

**Confidence**: high

When the target message has string content, the modification's `modified_content` replaces the entire content string.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-008 | high | A request with messages[0].content as string `original text` and a modification with message_index 0 and modified_content `redacted text` | `apply_modifications` is called | Function SHALL replace messages[0].content with `redacted text` |

---

### REQ-009: For multimodal content, modification writes to FIRST text part, clears remaining text parts, preserves image parts

**Confidence**: high

When the target message has multimodal (list) content, the modification's `modified_content` is written to the first text part. All remaining text parts are cleared (set to empty string). Image parts and other non-text parts are preserved unchanged. The overall list structure remains intact.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-009 | high | A request with messages[0].content as a list: `[{'type': 'text', 'text': 'A'}, {'type': 'image_url', 'image_url': {'url': '...'}}, {'type': 'text', 'text': 'B'}]` and a modification with message_index 0 and modified_content `modified` | `apply_modifications` is called | Function SHALL write `modified` to the first text part (at list index 0). The second text part (at list index 2) SHALL be cleared (set to empty string). image_url parts SHALL be preserved unchanged. The overall list structure SHALL remain intact. |

---

### REQ-010: Empty modifications list returns request unchanged

**Confidence**: high

When the modifications list is empty, `apply_modifications` returns the request without any changes.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-010 | high | A request with a messages array and an empty modifications list | `apply_modifications` is called with the empty list | Function SHALL return the request unchanged |

---

### REQ-011: ExtractedContent model has fields: message_index (int), role (str), text (str)

**Confidence**: high

The `ExtractedContent` Pydantic model is defined with three fields: `message_index` (int), `role` (str), and `text` (str). This model represents a single extracted detection unit from the messages array.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-011 | high | The ExtractedContent Pydantic model is defined | An ExtractedContent instance is created | Model SHALL have field `message_index` of type int. Model SHALL have field `role` of type str. Model SHALL have field `text` of type str. |

---

### REQ-012: Modification model has fields: detector_name (str), modified_content (str), priority (int), message_index (int)

**Confidence**: high

The `Modification` Pydantic model is defined with four fields: `detector_name` (str), `modified_content` (str), `priority` (int), and `message_index` (int). This model represents a detector's modification to be applied to a specific message in the request.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-012 | high | The Modification Pydantic model is defined | A Modification instance is created | Model SHALL have field `detector_name` of type str. Model SHALL have field `modified_content` of type str. Model SHALL have field `priority` of type int. Model SHALL have field `message_index` of type int. |
