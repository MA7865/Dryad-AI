
"""
M2 Vegetation Intelligence API.

Serves the precomputed vegetation GeoJSON.
"""

from fastapi import APIRouter, HTTPException, Query

from modules.vegetation.vegetation import predict_vegetation

router = APIRouter(
    prefix="/api/v1",
    tags=["Vegetation"]
)


@router.get("/layers/vegetation")
def get_vegetation_layer(
    patch_id: list[str] | None = Query(default=None),
    as_of: str | None = None
):
    """
    Return vegetation and anomaly data.

    Optional filters:
      patch_id: One or more patch IDs.
      as_of: Currently supports 2026 only.
    """

    try:
        return predict_vegetation(
            patch_ids=patch_id,
            as_of=as_of
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error)
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error
