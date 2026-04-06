"""Tests for read-only mode configuration and transform."""

import pytest
from mcp.types import ToolAnnotations

from ha_mcp.transforms.read_only import ReadOnlyTransform

# ---------------------------------------------------------------------------
# ReadOnlyTransform unit tests
# ---------------------------------------------------------------------------


def _make_tool(name: str, *, read_only: bool) -> "Tool":  # noqa: F821
    """Create a minimal Tool-like object for testing."""
    from fastmcp.tools import Tool

    async def _noop() -> str:
        return "ok"

    annotations = (
        ToolAnnotations(readOnlyHint=True)
        if read_only
        else ToolAnnotations(destructiveHint=True)
    )
    return Tool.from_function(
        fn=_noop,
        name=name,
        description=f"Test tool {name}",
        annotations=annotations,
    )


class TestReadOnlyTransform:
    """Verify the ReadOnlyTransform filters tools correctly."""

    @pytest.fixture()
    def transform(self) -> ReadOnlyTransform:
        return ReadOnlyTransform()

    @pytest.fixture()
    def mixed_tools(self) -> list:
        return [
            _make_tool("ha_get_states", read_only=True),
            _make_tool("ha_search_entities", read_only=True),
            _make_tool("ha_set_entity", read_only=False),
            _make_tool("ha_remove_area", read_only=False),
            _make_tool("ha_get_history", read_only=True),
        ]

    async def test_list_tools_filters_destructive(self, transform, mixed_tools):
        result = await transform.list_tools(mixed_tools)
        names = [t.name for t in result]
        assert names == ["ha_get_states", "ha_search_entities", "ha_get_history"]

    async def test_list_tools_empty_when_all_destructive(self, transform):
        tools = [
            _make_tool("ha_set_entity", read_only=False),
            _make_tool("ha_remove_area", read_only=False),
        ]
        result = await transform.list_tools(tools)
        assert list(result) == []

    async def test_list_tools_all_when_all_read_only(self, transform):
        tools = [
            _make_tool("ha_get_states", read_only=True),
            _make_tool("ha_get_history", read_only=True),
        ]
        result = await transform.list_tools(tools)
        assert len(result) == 2

    async def test_list_tools_empty_input(self, transform):
        result = await transform.list_tools([])
        assert list(result) == []


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestReadOnlyConfig:
    """Verify the READ_ONLY setting is loaded correctly."""

    def test_default_is_false(self):
        from ha_mcp.config import Settings

        settings = Settings(
            HOMEASSISTANT_URL="http://test:8123",
            HOMEASSISTANT_TOKEN="test-token",
        )  # type: ignore[call-arg]
        assert settings.read_only is False

    def test_read_only_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("READ_ONLY", "true")
        from ha_mcp.config import Settings

        settings = Settings(
            HOMEASSISTANT_URL="http://test:8123",
            HOMEASSISTANT_TOKEN="test-token",
        )  # type: ignore[call-arg]
        assert settings.read_only is True

    def test_read_only_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("READ_ONLY", "false")
        from ha_mcp.config import Settings

        settings = Settings(
            HOMEASSISTANT_URL="http://test:8123",
            HOMEASSISTANT_TOKEN="test-token",
        )  # type: ignore[call-arg]
        assert settings.read_only is False
