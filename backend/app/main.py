from fastapi import FastAPI

from backend.app.api import forest_health, ignition_risk, weather

app = FastAPI(title="Dryad.AI API")
app.include_router(forest_health.router)
app.include_router(ignition_risk.router)
app.include_router(weather.router)
@app.get("/")
def root():
    return {"service": "Dryad.AI API", "docs": "/docs"}