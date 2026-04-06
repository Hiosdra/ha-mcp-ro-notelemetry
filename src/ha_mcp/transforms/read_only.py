"""Read-only transform for ha-mcp.

When ``READ_ONLY=true`` is set, this transform removes every tool that
is **not** annotated with ``readOnlyHint=True``, ensuring the server
exposes only safe, non-mutating operations.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from fastmcp.server.transforms import Transform
from fastmcp.tools import Tool

if TYPE_CHECKING:
    from fastmcp.server.transforms import GetToolNext
    from fastmcp.utilities.versions import VersionSpec

logger = logging.getLogger(__name__)


class ReadOnlyTransform(Transform):
    """Filter the tool catalog to read-only tools.

    A tool is considered read-only when its MCP annotations include
    ``readOnlyHint=True``.  All other tools are silently dropped from
    ``list_tools`` and ``get_tool`` responses.
    """

    @staticmethod
    def _is_read_only(tool: Tool) -> bool:
        return bool(tool.annotations and tool.annotations.readOnlyHint)

    async def list_tools(self, tools: Sequence[Tool]) -> Sequence[Tool]:
        filtered = [t for t in tools if self._is_read_only(t)]
        logger.info(
            "Read-only mode: exposing %d/%d tools",
            len(filtered),
            len(tools),
        )
        return filtered

    async def get_tool(
        self,
        name: str,
        call_next: GetToolNext,
        *,
        version: VersionSpec | None = None,
    ) -> Tool | None:
        tool = await call_next(name, version=version)
        if tool is None:
            return None
        if self._is_read_only(tool):
            return tool
        logger.debug(
            "Read-only mode: blocked access to non-read-only tool '%s'",
            name,
        )
        return None
