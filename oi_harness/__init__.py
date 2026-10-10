"""oi-harness: production-grade Harness Agent on top of LangChain Deep Agents."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from oi_harness._version import __version__
from oi_harness.config import (
    HarnessAgentConfig,
    MediaGenerationConfig,
    MediaProviderConfig,
    ModelConfig,
    ProviderConfig,
)
from oi_harness.request import ChatRequest

if TYPE_CHECKING:
    from oi_harness.agent import HarnessAgent
    from oi_harness.init import InitResult, init_workspace
    from oi_harness.manager import AgentEntry, HarnessAgentManager
    from oi_harness.observability.logging import (
        current_log_file,
        default_log_dir,
        setup_logging,
        teardown_logging,
    )
    from oi_harness.protocols.langgraph import AgentEventType
    from oi_harness.providers import ModelPreset, ProviderPreset

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AgentEntry": ("oi_harness.manager", "AgentEntry"),
    "HarnessAgentManager": ("oi_harness.manager", "HarnessAgentManager"),
    "ModelPreset": ("oi_harness.providers", "ModelPreset"),
    "ProviderPreset": ("oi_harness.providers", "ProviderPreset"),
    "HarnessAgent": ("oi_harness.agent", "HarnessAgent"),
    "InitResult": ("oi_harness.init", "InitResult"),
    "init_workspace": ("oi_harness.init", "init_workspace"),
    "current_log_file": ("oi_harness.observability.logging", "current_log_file"),
    "default_log_dir": ("oi_harness.observability.logging", "default_log_dir"),
    "setup_logging": ("oi_harness.observability.logging", "setup_logging"),
    "teardown_logging": ("oi_harness.observability.logging", "teardown_logging"),
    "ChatProtocol": ("oi_harness.protocols", "ChatProtocol"),
    "register_protocol": ("oi_harness.protocols", "register_protocol"),
    "resolve_protocol": ("oi_harness.protocols", "resolve_protocol"),
    "AgentEventType": ("oi_harness.protocols.langgraph", "AgentEventType"),
    "SecurityPolicy": ("oi_harness.security.models", "SecurityPolicy"),
}


def __getattr__(name: str) -> object:  # pragma: no cover - thin re-export shim
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    return getattr(import_module(module_name), attr)


__all__ = [
    "AgentEntry",
    "AgentEventType",
    "ChatProtocol",
    "ChatRequest",
    "HarnessAgent",
    "HarnessAgentConfig",
    "HarnessAgentManager",
    "InitResult",
    "MediaGenerationConfig",
    "MediaProviderConfig",
    "ModelConfig",
    "ModelPreset",
    "ProviderConfig",
    "ProviderPreset",
    "SecurityPolicy",
    "__version__",
    "current_log_file",
    "default_log_dir",
    "init_workspace",
    "register_protocol",
    "resolve_protocol",
    "setup_logging",
    "teardown_logging",
]
