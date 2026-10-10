"""Backward-compat re-export — prefer ``from oi_harness.slash import ...``."""

from oi_harness.slash.core import (
    RuntimeSlashDispatcher,
    build_runtime_dispatcher,
)

__all__ = ["RuntimeSlashDispatcher", "build_runtime_dispatcher"]
