import os

os.environ.setdefault("M1_LIVE", "off")      # no Earth Engine calls

from fastapi.testclient import TestClient

from backend.app.main import app

c = TestClient(app)
for url in ("/api/v1/layers/forest-health/status",
            "/api/v1/patches/P_r000_c024/forest-health",
            "/api/v1/patches/NOPE/forest-health"):
    print(c.get(url).status_code, url)
r = c.get("/api/v1/layers/forest-health")
print(r.status_code, len(r.json()["features"]), "patches (summer layer)")