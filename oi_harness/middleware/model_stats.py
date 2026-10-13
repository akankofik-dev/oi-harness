"""Latency stats helper for smart model routing.

Stores per-model call latency statistics in a small JSON file so that
``pick_default_model_ref()`` can prefer the fastest enabled model.

All I/O is fail-open: every public function swallows exceptions and never
raises, so a missing or corrupted stats file can never break chat.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

# EWMA weight for the rolling average latency.
EWMA_ALPHA = 0.3

# A model is considered "bad" (skipped by routing) when it has more than
# this many errors AND its error rate exceeds this fraction.
MAX_ERRORS = 5
MAX_ERROR_RATE = 0.5


def get_stats_path() -> Path:
    """Return the stats file path (overridable via ``OI_MODEL_STATS_PATH``)."""
    return Path(os.environ.get("OI_MODEL_STATS_PATH", "~/.oi/model-stats.json")).expanduser()


def load_stats() -> dict:
    """Load the stats dict, or {} when the file is missing/corrupt (fail-open)."""
    try:
        path = get_stats_path()
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_stats(stats: dict) -> None:
    """Write stats atomically (temp file + rename). Fail-open: never raises."""
    try:
        path = get_stats_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".model-stats-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(stats, f)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        pass


def record_call(model_ref: str, latency_s: float, ok: bool) -> None:
    """Record one completed call. Updates EWMA avg, n, err, last. Fail-open."""
    try:
        if not model_ref:
            return
        stats = load_stats()
        models = stats.get("models")
        if not isinstance(models, dict):
            models = {}
            stats["models"] = models
        entry = models.get(model_ref)
        if not isinstance(entry, dict):
            entry = {}
        try:
            n = int(entry.get("n", 0)) + 1
        except (TypeError, ValueError):
            n = 1
        try:
            prev_avg = float(entry.get("avg", 0.0))
        except (TypeError, ValueError):
            prev_avg = 0.0
        try:
            latency = max(0.0, float(latency_s))
        except (TypeError, ValueError):
            latency = 0.0
        # EWMA: first sample seeds the average, subsequent samples blend.
        if n == 1:
            avg = latency
        else:
            avg = EWMA_ALPHA * latency + (1.0 - EWMA_ALPHA) * prev_avg
        try:
            err = int(entry.get("err", 0))
        except (TypeError, ValueError):
            err = 0
        if not ok:
            err += 1
        now = time.time()
        models[model_ref] = {"avg": avg, "n": n, "err": err, "last": now}
        stats["updated_at"] = now
        save_stats(stats)
    except Exception:
        pass


def _is_bad(entry: dict) -> bool:
    """True when the model has many errors and a high error rate."""
    try:
        err = int(entry.get("err", 0))
        n = int(entry.get("n", 0))
    except (TypeError, ValueError):
        return False
    if n <= 0:
        return False
    return err > MAX_ERRORS and (err / n) > MAX_ERROR_RATE


def pick_fastest_model_ref(refs: list) -> str | None:
    """Return the ref with the lowest avg latency.

    Models with no stats are treated as avg=+inf (prioritized last).
    Models with high error counts/rates are skipped unless all are bad.
    Fail-open: never raises; returns None when nothing is usable.
    """
    try:
        if not refs:
            return None
        stats = load_stats()
        models = stats.get("models")
        if not isinstance(models, dict):
            models = {}

        def score(ref: str) -> float:
            entry = models.get(ref)
            if not isinstance(entry, dict):
                return float("inf")
            try:
                return float(entry.get("avg", float("inf")))
            except (TypeError, ValueError):
                return float("inf")

        good = [r for r in refs if not _is_bad(models.get(r, {}))]
        pool = good if good else list(refs)
        if not pool:
            return None
        return min(pool, key=score)
    except Exception:
        return None
