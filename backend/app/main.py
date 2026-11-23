from fastapi import FastAPI

from backend.app.api import fires, forest_health

app = FastAPI(title="Dryad.AI API")
app.include_router(forest_health.router)
app.include_router(fires.router)
@app.get("/")
def root():
    return {"service": "Dryad.AI API", "docs": "/docs"}