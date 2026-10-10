"""Custom middleware shipped with oi-harness."""

from __future__ import annotations

from oi_harness.middleware.client_tool_search import ClientToolSearchMiddleware
from oi_harness.middleware.conversation_mode import ConversationModeMiddleware
from oi_harness.middleware.filesystem_guard import FilesystemGuardMiddleware
from oi_harness.middleware.media_offload import MediaOffloadMiddleware
from oi_harness.middleware.memory import MemoryMiddleware
from oi_harness.middleware.model_settings import (
    CONFIGURABLE_MAX_INPUT_TOKENS,
    CONFIGURABLE_MODEL_SETTINGS,
    ModelSettingsMiddleware,
)
from oi_harness.middleware.native_tool_search import NativeToolSearchMiddleware
from oi_harness.middleware.peer import PeerAgentMiddleware
from oi_harness.middleware.pii import detect_pii
from oi_harness.middleware.tool_search import ToolSearchMiddleware

__all__ = [
    "CONFIGURABLE_MAX_INPUT_TOKENS",
    "CONFIGURABLE_MODEL_SETTINGS",
    "ClientToolSearchMiddleware",
    "ConversationModeMiddleware",
    "FilesystemGuardMiddleware",
    "MediaOffloadMiddleware",
    "MemoryMiddleware",
    "ModelSettingsMiddleware",
    "NativeToolSearchMiddleware",
    "PeerAgentMiddleware",
    "ToolSearchMiddleware",
    "detect_pii",
]
