"""Tests for apply_modifications() function."""

from __future__ import annotations

from z_llm_safety_gateway.content.writeback import apply_modifications
from z_llm_safety_gateway.models import Modification


class TestApplyModifications:
    """Tests for apply_modifications function covering TC-EXTRACT-007 through TC-EXTRACT-010."""

    def test_apply_modifications_sorted_by_priority_ascending(self) -> None:
        """TC-EXTRACT-007: priorities [20, 10, 100] applied in order 10, 20, 100."""
        request: dict = {
            "messages": [
                {"role": "user", "content": "original"},
            ]
        }
        modifications = [
            Modification(
                detector_name="det_c", modified_content="applied_third", priority=20,
                message_index=0,
            ),
            Modification(
                detector_name="det_a", modified_content="applied_first", priority=10,
                message_index=0,
            ),
            Modification(
                detector_name="det_b", modified_content="applied_last", priority=100,
                message_index=0,
            ),
        ]

        result = apply_modifications(request, modifications)

        # Priority 100 is applied last, so final content should be "applied_last"
        assert result["messages"][0]["content"] == "applied_last"

    def test_apply_modifications_string_content_replaced(self) -> None:
        """TC-EXTRACT-008: string content replaced by modified_content."""
        request: dict = {
            "messages": [
                {"role": "user", "content": "original text"},
            ]
        }
        modifications = [
            Modification(
                detector_name="pii_detector",
                modified_content="redacted text",
                priority=10,
                message_index=0,
            ),
        ]

        result = apply_modifications(request, modifications)

        assert result["messages"][0]["content"] == "redacted text"

    def test_apply_modifications_multimodal_first_text_replaced_rest_cleared(self) -> None:
        """TC-EXTRACT-009: first text part set, rest cleared, image preserved."""
        request: dict = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "A"},
                        {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
                        {"type": "text", "text": "B"},
                    ],
                },
            ]
        }
        modifications = [
            Modification(
                detector_name="pii_detector",
                modified_content="modified",
                priority=10,
                message_index=0,
            ),
        ]

        result = apply_modifications(request, modifications)

        content = result["messages"][0]["content"]
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "modified"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"] == {"url": "https://example.com/img.png"}
        assert content[2]["type"] == "text"
        assert content[2]["text"] == ""

    def test_apply_modifications_empty_list_returns_request_unchanged(self) -> None:
        """TC-EXTRACT-010: empty modifications list returns request unchanged."""
        request: dict = {
            "messages": [
                {"role": "user", "content": "unchanged"},
            ]
        }

        result = apply_modifications(request, [])

        assert result == request

    def test_apply_modifications_does_not_mutate_original_request(self) -> None:
        """Edge case: apply_modifications should not modify the original request dict."""
        original_request: dict = {
            "messages": [
                {"role": "user", "content": "original"},
            ]
        }
        modifications = [
            Modification(
                detector_name="det",
                modified_content="modified",
                priority=10,
                message_index=0,
            ),
        ]

        result = apply_modifications(original_request, modifications)

        # Original request should be unchanged
        assert original_request["messages"][0]["content"] == "original"
        # Result should have modified content
        assert result["messages"][0]["content"] == "modified"

    def test_apply_modifications_different_message_indices(self) -> None:
        """Edge case: modifications targeting different messages."""
        request: dict = {
            "messages": [
                {"role": "system", "content": "system original"},
                {"role": "user", "content": "user original"},
            ]
        }
        modifications = [
            Modification(
                detector_name="det1",
                modified_content="user modified",
                priority=10,
                message_index=1,
            ),
            Modification(
                detector_name="det2",
                modified_content="system modified",
                priority=20,
                message_index=0,
            ),
        ]

        result = apply_modifications(request, modifications)

        assert result["messages"][0]["content"] == "system modified"
        assert result["messages"][1]["content"] == "user modified"

    def test_apply_modifications_multimodal_single_text_part(self) -> None:
        """Edge case: multimodal content with only one text part."""
        request: dict = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "original text"},
                        {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
                    ],
                },
            ]
        }
        modifications = [
            Modification(
                detector_name="det",
                modified_content="new text",
                priority=10,
                message_index=0,
            ),
        ]

        result = apply_modifications(request, modifications)

        content = result["messages"][0]["content"]
        assert content[0]["text"] == "new text"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"] == {"url": "https://example.com/img.png"}
