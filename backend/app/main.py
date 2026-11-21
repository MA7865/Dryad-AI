from fastapi import FastAPI

from backend.app.api import forest_health

app = FastAPI(title="Dryad.AI API")
app.include_router(forest_health.router)
@app.get("/")
def root():
    return {"service": "Dryad.AI API", "docs": "/docs"}