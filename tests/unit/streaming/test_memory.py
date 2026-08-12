"""Unit tests for streaming memory management.

Covers TC-SSE-009 and TC-SSE-010 (sse-streaming spec).
"""

from __future__ import annotations

from z_llm_safety_gateway.streaming.memory import SizeLimit, StreamingMemory


# --------------------------------------------------------------------------- #
# TC-SSE-009: max_response_size block policy
# --------------------------------------------------------------------------- #
def test_memory_block_when_exceeds_limit():
    """TC-SSE-009: exceeding max_response_size triggers block."""
    mem = StreamingMemory(max_response_size="1KB", on_max_size="block")
    # 1KB = 1024 bytes
    assert not mem.check_exceeded("a" * 500)
    exceeded = mem.check_exceeded("a" * 1024)
    assert exceeded is True


def test_memory_block_policy_type():
    """TC-SSE-009b: on_max_size block policy identified."""
    mem = StreamingMemory(max_response_size="1MB", on_max_size="block")
    assert mem.policy == "block"


def test_size_limit_parse():
    """TC-SSE-009c: size strings like '1MB' parse to bytes."""
    assert SizeLimit.parse("1KB") == 1024
    assert SizeLimit.parse("1MB") == 1024 * 1024
    assert SizeLimit.parse("512") == 512


# --------------------------------------------------------------------------- #
# TC-SSE-010: max_response_size truncate policy
# --------------------------------------------------------------------------- #
def test_memory_truncate_policy_type():
    """TC-SSE-010: on_max_size truncate policy identified."""
    mem = StreamingMemory(max_response_size="1MB", on_max_size="truncate")
    assert mem.policy == "truncate"


def test_memory_utf8_chinese_bytes():
    """TC-SSE-016: UTF-8 Chinese chars counted as 3 bytes each."""
    mem = StreamingMemory(max_response_size="1KB", on_max_size="block")
    # "你" is 3 bytes in UTF-8
    chinese_content = "你" * 341  # 341 * 3 = 1023 bytes < 1024
    assert not mem.check_exceeded(chinese_content)
    chinese_content2 = "你" * 342  # 342 * 3 = 1026 bytes > 1024
    assert mem.check_exceeded(chinese_content2)
