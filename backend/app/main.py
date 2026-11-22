
from fastapi import FastAPI

from backend.app.api import forest_health
from backend.app.api import vegetation

app = FastAPI(title="Dryad.AI API")

# Member 1 - Forest Health
app.include_router(forest_health.router)

# Member 2 - Vegetation & Anomaly
app.include_router(vegetation.router)


@app.get("/")
def root():
    return {
        "service": "Dryad.AI API",
        "docs": "/docs"
    }
