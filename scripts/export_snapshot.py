"""
export_snapshot.py -- saves frontend-ready JSON files so the UI can be built without the API running.
    python -m scripts.export_snapshot
Writes frontend_snapshot/*.json (not committed)
"""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app

OUT = Path("frontend_snapshot")
OUT.mkdir(exist_ok=True)
c = TestClient(app)
jobs = {
    "layer_summer_latest.json": "/api/v1/layers/forest-health",
    "layer_2022_summer.json": "/api/v1/layers/forest-health?year=2022",
    "layer_live.json": "/api/v1/layers/forest-health?period=live",
    "timeline.json": "/api/v1/layers/forest-health/timeline",
    "status.json": "/api/v1/layers/forest-health/status",
    "model_card.json": "/api/v1/layers/forest-health/model-card",
    "patch_example.json": "/api/v1/patches/P_r000_c024/forest-health",
}
for name, url in jobs.items():
    r = c.get(url)
    print(r.status_code, url, f"{len(r.content) / 1024:.0f} KB")
    if r.status_code == 200:
        (OUT / name).write_bytes(r.content)