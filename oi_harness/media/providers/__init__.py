"""Built-in media generation provider adapters."""

from oi_harness.media.providers.dashscope import DashScopeMediaProvider
from oi_harness.media.providers.minimax import MiniMaxMediaProvider
from oi_harness.media.providers.volcengine import VolcengineMediaProvider

__all__ = ["DashScopeMediaProvider", "MiniMaxMediaProvider", "VolcengineMediaProvider"]
