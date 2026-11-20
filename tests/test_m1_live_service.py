import pytest

from modules.forest_health import live_service, refresh

FAKE_LAYER = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": None,
     "properties": {"patch_id": "P_r000_c000", "health_index": 50}}]}
FAKE_META = {"mode": "live", "generated_at": "2026-01-01T00:00:00Z"}


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(live_service, "CACHE", tmp_path)
    monkeypatch.setattr(live_service, "LIVE", tmp_path / "live.geojson")
    monkeypatch.setattr(live_service, "LIVE_META", tmp_path / "meta.json")
    monkeypatch.setattr(live_service, "ENABLED", True)
    live_service._state.update(layer=None, meta=None, props={}, built_at=0.0,
                               running=False, error=None, last_attempt=0.0)
    return live_service


def test_refresh_builds_and_caches(svc, monkeypatch):
    monkeypatch.setattr(refresh, "build_live", lambda: (FAKE_LAYER, FAKE_META))
    svc._state["running"] = True
    svc._worker()
    layer, meta, props, status = svc.get_live()
    assert layer == FAKE_LAYER
    assert "P_r000_c000" in props
    assert status["error"] is None
    assert svc.LIVE.exists()


def test_failed_refresh_keeps_old_data(svc, monkeypatch):
    monkeypatch.setattr(refresh, "build_live", lambda: (FAKE_LAYER, FAKE_META))
    svc._state["running"] = True
    svc._worker()

    def boom():
        raise RuntimeError("Earth Engine unavailable")

    monkeypatch.setattr(refresh, "build_live", boom)
    svc._state["running"] = True
    svc._worker()
    layer, _, _, status = svc.get_live()
    assert layer == FAKE_LAYER                         # old data still served
    assert "Earth Engine unavailable" in status["error"]


def test_disabled_never_calls_earth_engine(svc, monkeypatch):
    monkeypatch.setattr(svc, "ENABLED", False)
    called = []
    monkeypatch.setattr(refresh, "build_live", lambda: called.append(1))
    layer, _, _, status = svc.get_live()
    assert layer is None and status["enabled"] is False and not called