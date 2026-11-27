from fastapi import FastAPI

from backend.app.api import fires, forest_health, vegetation

import os

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(title="Dryad.AI API")

# Member 1 - Forest Health
app.include_router(forest_health.router)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["*"])
# Member 2 - Vegetation & Anomaly
app.include_router(vegetation.router)

# Member 4 - Fire monitoring and spread
app.include_router(fires.router)


@app.get("/")
def root():
    return {
        "service": "Dryad.AI API",
        "docs": "/docs"
    }
