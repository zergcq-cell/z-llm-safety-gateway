"""Tests for Pydantic models: ExtractedContent and Modification."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from z_llm_safety_gateway.models import ExtractedContent, Modification


class TestExtractedContentModel:
    """TC-EXTRACT-011: ExtractedContent model field definitions."""

    def test_extracted_content_model_has_required_fields(self) -> None:
        """TC-EXTRACT-011: ExtractedContent has message_index, role, text."""
        ec = ExtractedContent(message_index=0, role="user", text="Hello world")

        assert ec.message_index == 0
        assert ec.role == "user"
        assert ec.text == "Hello world"

    def test_extracted_content_is_basemodel_subclass(self) -> None:
        """TC-EXTRACT-011: ExtractedContent should be a Pydantic BaseModel."""
        assert issubclass(ExtractedContent, BaseModel)

    def test_extracted_content_message_index_type_is_int(self) -> None:
        """TC-EXTRACT-011: message_index field should be int type."""
        ec = ExtractedContent(message_index=5, role="system", text="test")
        assert isinstance(ec.message_index, int)

    def test_extracted_content_role_type_is_str(self) -> None:
        """TC-EXTRACT-011: role field should be str type."""
        ec = ExtractedContent(message_index=0, role="developer", text="test")
        assert isinstance(ec.role, str)

    def test_extracted_content_text_type_is_str(self) -> None:
        """TC-EXTRACT-011: text field should be str type."""
        ec = ExtractedContent(message_index=0, role="user", text="some text")
        assert isinstance(ec.text, str)


class TestModificationModel:
    """TC-EXTRACT-012: Modification model field definitions."""

    def test_modification_model_has_required_fields(self) -> None:
        """TC-EXTRACT-012: Modification has all four required fields."""
        mod = Modification(
            detector_name="pii_detector",
            modified_content="redacted text",
            priority=10,
            message_index=0,
        )

        assert mod.detector_name == "pii_detector"
        assert mod.modified_content == "redacted text"
        assert mod.priority == 10
        assert mod.message_index == 0

    def test_modification_is_basemodel_subclass(self) -> None:
        """TC-EXTRACT-012: Modification should be a Pydantic BaseModel."""
        assert issubclass(Modification, BaseModel)

    def test_modification_detector_name_type_is_str(self) -> None:
        """TC-EXTRACT-012: detector_name field should be str type."""
        mod = Modification(
            detector_name="test", modified_content="x", priority=1, message_index=0
        )
        assert isinstance(mod.detector_name, str)

    def test_modification_modified_content_type_is_str(self) -> None:
        """TC-EXTRACT-012: modified_content field should be str type."""
        mod = Modification(
            detector_name="test", modified_content="x", priority=1, message_index=0
        )
        assert isinstance(mod.modified_content, str)

    def test_modification_priority_type_is_int(self) -> None:
        """TC-EXTRACT-012: priority field should be int type."""
        mod = Modification(
            detector_name="test", modified_content="x", priority=42, message_index=0
        )
        assert isinstance(mod.priority, int)

    def test_modification_message_index_type_is_int(self) -> None:
        """TC-EXTRACT-012: message_index field should be int type."""
        mod = Modification(
            detector_name="test", modified_content="x", priority=1, message_index=3
        )
        assert isinstance(mod.message_index, int)

    def test_modification_invalid_priority_type_raises_error(self) -> None:
        """TC-EXTRACT-012: priority must be int, string should raise ValidationError."""
        with pytest.raises(ValidationError):
            Modification(
                detector_name="test",
                modified_content="x",
                priority="not_an_int",  # type: ignore[arg-type]
                message_index=0,
            )
