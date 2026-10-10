"""Memory adapter helpers for oi-harness.

The public surface of this subpackage is :class:`MemoryRuntime`, which wires
:class:`oi_memory.Memory` / :class:`oi_memory.MemoryService` into the
agent.

:class:`oi_harness.memory.llm_client.HarnessAgentLLMClient` is an internal
adapter used by :class:`MemoryRuntime` to expose the agent's
:class:`~oi_harness.llm.factory.ChatModelFactory` to oi-memory's
extractor / promotion / page-regeneration paths via the
:class:`oi_memory.ports.llm.LLMClient` protocol. It is intentionally not
re-exported here: callers who need a custom LLM client should implement the
``LLMClient`` protocol directly rather than subclassing or constructing this
adapter themselves.
"""

from __future__ import annotations

from oi_harness.memory.runtime import MemoryRuntime

__all__ = ["MemoryRuntime"]
