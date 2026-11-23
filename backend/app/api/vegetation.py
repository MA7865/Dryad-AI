
"""
M2 Vegetation Intelligence API.

Serves validated, precomputed GeoJSON.
Does not run GEE during API requests.
"""

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.vegetation import (
    VegetationFeatureCollection,
)
from modules.vegetation.vegetation import (
    predict_vegetation,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Vegetation"],
)


@router.get(
    "/layers/vegetation",
    response_model=VegetationFeatureCollection,
    summary="Get vegetation and anomaly layer",
)
def get_vegetation_layer(
    patch_id: list[str] | None = Query(
        default=None,
        description="Optional repeated patch ID filter",
    ),
    as_of: str | None = Query(
        default=None,
        description="Currently supports 2026 only",
    ),
):
    """
    Return LANDFIRE vegetation classifications,
    satellite measurements, burn context and
    exploratory statistical anomaly results.

    Repeated patch_id parameters select multiple patches.
    Missing detection results are returned as null.
    """

    try:
        return predict_vegetation(
            patch_ids=patch_id,
            as_of=as_of,
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
