"""Tests for extract_content() function."""

from __future__ import annotations

from z_llm_safety_gateway.content.extractor import extract_content
from z_llm_safety_gateway.models import ExtractedContent


class TestExtractContent:
    """Tests for extract_content function covering TC-EXTRACT-001 through TC-EXTRACT-006."""

    def test_extract_content_user_system_developer_roles_returned(self) -> None:
        """TC-EXTRACT-001: user, system, developer roles each return ExtractedContent."""
        messages = [
            {"role": "user", "content": "user msg"},
            {"role": "system", "content": "system msg"},
            {"role": "developer", "content": "developer msg"},
        ]

        result = extract_content(messages)

        assert len(result) == 3
        assert all(isinstance(item, ExtractedContent) for item in result)
        assert result[0].role == "user"
        assert result[1].role == "system"
        assert result[2].role == "developer"

    def test_extract_content_assistant_function_tool_roles_skipped(self) -> None:
        """TC-EXTRACT-002: assistant, function, tool roles are not extracted."""
        messages = [
            {"role": "assistant", "content": "assistant msg"},
            {"role": "function", "content": "function msg"},
            {"role": "tool", "content": "tool msg"},
        ]

        result = extract_content(messages)

        assert len(result) == 0

    def test_extract_content_string_content_extracted_directly(self) -> None:
        """TC-EXTRACT-003: string content 'Hello world' is extracted as text."""
        messages = [
            {"role": "user", "content": "Hello world"},
        ]

        result = extract_content(messages)

        assert len(result) == 1
        assert result[0].text == "Hello world"

    def test_extract_content_multimodal_text_part_extracted_image_skipped(self) -> None:
        """TC-EXTRACT-004: multimodal content with text and image_url, only text extracted."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
                ],
            },
        ]

        result = extract_content(messages)

        assert len(result) == 1
        assert result[0].text == "Describe this"

    def test_extract_content_multiple_text_parts_joined_with_newline(self) -> None:
        """TC-EXTRACT-005: multiple text parts in multimodal content joined with newline."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Line 1"},
                    {"type": "text", "text": "Line 2"},
                ],
            },
        ]

        result = extract_content(messages)

        assert len(result) == 1
        assert result[0].text == "Line 1\nLine 2"

    def test_extract_content_message_index_and_role_preserved(self) -> None:
        """TC-EXTRACT-006: message_index reflects original array position, not sequential count."""
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user query"},
            {"role": "assistant", "content": "assistant response"},
        ]

        result = extract_content(messages)

        assert len(result) == 2
        assert result[0].message_index == 0
        assert result[0].role == "system"
        assert result[1].message_index == 1
        assert result[1].role == "user"

    def test_extract_content_empty_messages_returns_empty_list(self) -> None:
        """Edge case: empty messages list returns empty list."""
        result = extract_content([])

        assert result == []

    def test_extract_content_mixed_roles_only_user_system_developer_returned(self) -> None:
        """Edge case: mixed roles, only user/system/developer extracted with correct indices."""
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "asst"},
            {"role": "user", "content": "usr"},
            {"role": "tool", "content": "tool"},
            {"role": "developer", "content": "dev"},
        ]

        result = extract_content(messages)

        assert len(result) == 3
        assert result[0].message_index == 0
        assert result[0].role == "system"
        assert result[1].message_index == 2
        assert result[1].role == "user"
        assert result[2].message_index == 4
        assert result[2].role == "developer"
