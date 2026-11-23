"""
live_service.py -- keeps the live layer fresh in memory, computed from Earth Engine in a
background thread, so nothing large has to live in the repo.

ensure_fresh() -> start a background refresh if there is no data or it is older than the TTL
get_live()     -> (layer, meta, props_by_patch, status)

Environment: M1_LIVE=off disables Earth Engine calls (tests, teammates without access);
             M1_LIVE_TTL_HOURS sets the refresh interval (default 6).
"""
import json
import os
import threading
import time

from .paths import CACHE, LIVE, LIVE_META

TTL_SECONDS = int(os.getenv("M1_LIVE_TTL_HOURS", "6")) * 3600
ENABLED = os.getenv("M1_LIVE", "on").lower() != "off"

_lock = threading.Lock()
_state = {"layer": None, "meta": None, "props": {}, "built_at": 0.0,
          "running": False, "error": None, "last_attempt": 0.0}


def _set(layer, meta, built_at) -> None:
    _state.update(
        layer=layer, meta=meta, built_at=built_at, error=None,
        props={f["properties"]["patch_id"]: f["properties"] for f in layer["features"]})


def _load_disk() -> None:
    if _state["layer"] is None and LIVE.exists() and LIVE_META.exists():
        _set(json.loads(LIVE.read_text()), json.loads(LIVE_META.read_text()),
             LIVE.stat().st_mtime)


def _worker() -> None:
    try:
        from .refresh import build_live          # Earth Engine is imported only here
        layer, meta = build_live()
        CACHE.mkdir(parents=True, exist_ok=True)
        LIVE.write_text(json.dumps(layer, separators=(",", ":"), allow_nan=False))
        LIVE_META.write_text(json.dumps(meta, indent=2))
        with _lock:
            _set(layer, meta, time.time())
    except Exception as exc:                      # keep serving the old data
        with _lock:
            _state["error"] = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        with _lock:
            _state["running"] = False


def ensure_fresh() -> None:
    with _lock:
        _load_disk()
        stale = _state["layer"] is None or (time.time() - _state["built_at"]) > TTL_SECONDS
        if not ENABLED or _state["running"] or not stale:
            return
        if time.time() - _state["last_attempt"] < 300:     # wait 5 minutes between attempts
            return
        _state["running"] = True
        _state["last_attempt"] = time.time()
    threading.Thread(target=_worker, daemon=True).start()


def get_live():
    ensure_fresh()
    with _lock:
        age = None if not _state["built_at"] else round((time.time() - _state["built_at"]) / 60)
        status = {"enabled": ENABLED, "refreshing": _state["running"],
                  "error": _state["error"], "age_minutes": age}
        return _state["layer"], _state["meta"], _state["props"], status