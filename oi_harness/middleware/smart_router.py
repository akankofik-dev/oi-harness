"""``SmartRouterMiddleware`` — latency-aware auto-failover per model call.

- Times each model call and records latency via model_stats (for Target 1).
- On retryable errors (timeout, HTTP 5xx/429, connection), retry with the
  fastest healthy backup model — MAX 3 attempts total per call, then raise.
- NEVER infinite loop. NEVER modifies stream behavior.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)

from oi_harness.middleware.model_stats import pick_fastest_model_ref, record_call

if TYPE_CHECKING:
    from oi_harness.config import HarnessAgentConfig
    from oi_harness.llm.factory import ChatModelFactory

logger = logging.getLogger(__name__)

# HTTP statuses that are safe to retry against a *different* model.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# HTTP statuses that must surface immediately (auth / client errors).
_NON_RETRYABLE_STATUS = frozenset({400, 401, 403, 404})

# Class-name fragments that are never retried (auth / permission / client).
_NON_RETRYABLE_NAME_FRAGMENTS = (
    "auth",
    "permission",
    "unauthorized",
    "forbidden",
    "badrequest",
    "notfound",
)

# Message fragments identifying context-length overflow — never retried so
# the user always sees the real error message.
_CONTEXT_MARKERS = (
    "context_length",
    "context length",
    "maximum context",
    "context window",
    "too many tokens",
    "token limit",
    "input too long",
    "prompt too long",
)


class SmartRouterMiddleware(AgentMiddleware[Any, Any]):
    """Latency-aware auto-failover around each already-resolved model call.

    Positioned directly after :class:`ModelRouterMiddleware`: attempt 0 uses
    the model instance it resolved (``request.model`` is never modified on
    the first attempt); later attempts swap ``request.model`` to the fastest
    untried healthy backup model.

    The attempt loop is strictly bounded by ``max_attempts`` — there is no
    ``while True`` anywhere. When every attempt fails, the last exception is
    re-raised unchanged.
    """

    def __init__(
        self,
        config: HarnessAgentConfig,
        factory: ChatModelFactory,
        *,
        max_attempts: int = 3,
        get_protocol: Callable[[str | None], Any] | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._factory = factory
        self._get_protocol = get_protocol
        self._max_attempts = max(1, int(max_attempts or 3))

    # ------------------------------------------------------------------
    # Middleware hooks (sync + async). Stream behavior is untouched.
    # ------------------------------------------------------------------
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        return self._call_with_failover(request, handler, is_async=False)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await self._call_with_failover(request, handler, is_async=True)

    def _call_with_failover(
        self,
        request: ModelRequest,
        handler: Callable[..., Any],
        is_async: bool,
    ) -> Any:
        """Dispatch to the bounded sync/async failover core."""
        if is_async:
            return self._acall_with_failover(request, handler)
        return self._scall_with_failover(request, handler)

    # ------------------------------------------------------------------
    # Failover cores — strictly bounded: ``for attempt in range(max_attempts)``
    # ------------------------------------------------------------------
    def _scall_with_failover(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        max_attempts = self._max_attempts
        tried: list[str] = []
        tried_set: set[str] = set()
        last_exc: BaseException | None = None
        initial_ref = self._initial_ref(request)

        for attempt in range(max_attempts):
            if attempt == 0:
                # Attempt 0: use the model ModelRouterMiddleware already
                # resolved. request.model is NOT modified here.
                ref = initial_ref
            else:
                ref = self._pick_backup(tried_set)
                if ref is None:
                    logger.debug(
                        "SmartRouter: no untried backup model left "
                        "(tried=%s); raising last error",
                        tried,
                    )
                    break
                try:
                    request.model = self._model_instance(ref)
                except Exception as exc:
                    # Could not even build the backup — record it and move on
                    # to the next candidate (still inside the bounded loop).
                    record_call(ref, 0.0, ok=False)
                    logger.debug("SmartRouter: backup %r build failed: %r", ref, exc)
                    tried.append(ref)
                    tried_set.add(ref)
                    continue
            if ref:
                tried.append(ref)
                tried_set.add(ref)
            t0 = time.perf_counter()
            try:
                resp = handler(request)
            except Exception as exc:
                record_call(ref, 0.0, ok=False)
                last_exc = exc
                if self._is_retryable(exc) and attempt < max_attempts - 1:
                    logger.debug(
                        "SmartRouter: attempt %d/%d with %r failed retryably "
                        "(%r); tried=%s; failing over",
                        attempt + 1,
                        max_attempts,
                        ref,
                        exc,
                        tried,
                    )
                    continue
                raise
            record_call(ref, time.perf_counter() - t0, ok=True)
            return resp

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("SmartRouterMiddleware: no model call was attempted")

    async def _acall_with_failover(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        max_attempts = self._max_attempts
        tried: list[str] = []
        tried_set: set[str] = set()
        last_exc: BaseException | None = None
        initial_ref = self._initial_ref(request)

        for attempt in range(max_attempts):
            if attempt == 0:
                ref = initial_ref
            else:
                ref = self._pick_backup(tried_set)
                if ref is None:
                    logger.debug(
                        "SmartRouter: no untried backup model left "
                        "(tried=%s); raising last error",
                        tried,
                    )
                    break
                try:
                    request.model = self._model_instance(ref)
                except Exception as exc:
                    record_call(ref, 0.0, ok=False)
                    logger.debug("SmartRouter: backup %r build failed: %r", ref, exc)
                    tried.append(ref)
                    tried_set.add(ref)
                    continue
            if ref:
                tried.append(ref)
                tried_set.add(ref)
            t0 = time.perf_counter()
            try:
                resp = await handler(request)
            except Exception as exc:
                record_call(ref, 0.0, ok=False)
                last_exc = exc
                if self._is_retryable(exc) and attempt < max_attempts - 1:
                    logger.debug(
                        "SmartRouter: attempt %d/%d with %r failed retryably "
                        "(%r); tried=%s; failing over",
                        attempt + 1,
                        max_attempts,
                        ref,
                        exc,
                        tried,
                    )
                    continue
                raise
            record_call(ref, time.perf_counter() - t0, ok=True)
            return resp

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("SmartRouterMiddleware: no model call was attempted")

    # ------------------------------------------------------------------
    # Ref resolution helpers
    # ------------------------------------------------------------------
    def _initial_ref(self, request: ModelRequest) -> str:
        """Return the ref already resolved by ModelRouterMiddleware (read-only).

        Prefers the ref it stamps on ``configurable["model"]``; falls back to
        the config default. Never raises — returns "" when unknown (stats
        recording simply no-ops on an empty ref).
        """
        try:
            from oi_harness.middleware.runtime import runtime_config

            cfg = runtime_config(request)
            if isinstance(cfg, dict):
                configurable = cfg.get("configurable")
                if isinstance(configurable, dict):
                    ref = configurable.get("model")
                    if ref:
                        return str(ref)
        except Exception:
            pass
        try:
            default = self._config.pick_default_model_ref()
            return str(default or "")
        except Exception:
            return ""

    def _enabled_refs(self) -> list[str]:
        """All enabled ``provider/model`` refs, fail-open."""
        try:
            refs: list[str] = []
            for provider in getattr(self._config, "providers", None) or []:
                for model in provider.enabled_models():
                    refs.append(f"{provider.id}/{model.id}")
            return refs
        except Exception:
            return []

    def _pick_backup(self, tried: set[str]) -> str | None:
        """Fastest enabled ref not yet tried (fail-open; None if none)."""
        candidates = [r for r in self._enabled_refs() if r not in tried]
        if not candidates:
            return None
        return pick_fastest_model_ref(candidates)

    def _model_instance(self, ref: str) -> Any:
        """Build the chat-model instance for ``ref`` (ModelRouter pattern)."""
        if self._get_protocol is not None:
            return self._factory.get(ref, get_protocol=self._get_protocol).chat_model
        return self._factory.get_chat_model(ref)

    # ------------------------------------------------------------------
    # Retryability policy
    # ------------------------------------------------------------------
    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        """True only for errors worth retrying against a different model.

        Retryable: timeouts, HTTP 429/500/502/503/504, connection errors.
        Never retried: auth/permission errors, HTTP 400/401/403/404, and
        context-length errors (the user must see those messages).
        Everything else defaults to False.
        """
        try:
            text = str(exc).lower()
        except Exception:
            text = ""
        # 1. Context-length overflow: never retry — surface the real message.
        if any(marker in text for marker in _CONTEXT_MARKERS):
            return False
        name = type(exc).__name__
        lname = name.lower()
        if "validation" in lname and ("context" in text or "length" in text):
            return False
        # 2. Auth / permission / client errors: never retry.
        if any(frag in lname for frag in _NON_RETRYABLE_NAME_FRAGMENTS):
            return False
        # 3. HTTP status, extracted defensively.
        status = getattr(exc, "status_code", None)
        if status is None:
            status = getattr(getattr(exc, "response", None), "status_code", None)
        try:
            status_code = int(status) if status is not None else None
        except (TypeError, ValueError):
            status_code = None
        # 3b. Status embedded in message text (e.g. "Error code: 503",
        # "HTTP 429") — some SDKs don't set a status_code attribute.
        if status_code is None:
            m = re.search(r"(?:error code|http)[\s:]+(\d{3})", text)
            if m:
                try:
                    status_code = int(m.group(1))
                except ValueError:
                    status_code = None
        if status_code in _NON_RETRYABLE_STATUS:
            return False
        # 4. Retryable conditions.
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return True
        if status_code in _RETRYABLE_STATUS:
            return True
        if "connect" in lname:  # ConnectionError, ConnectError, ConnectTimeout, ...
            return True
        if "timeout" in lname:  # httpx.TimeoutException, APITimeoutError, ...
            return True
        # 5. Default: do not retry.
        return False


__all__ = ["SmartRouterMiddleware"]
