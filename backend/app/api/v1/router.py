from fastapi import APIRouter

from app.concepts.router import router as concepts_router
from app.feedback.router import router as feedback_router
from app.market_data.router import router as market_data_router
from app.narrative_engine.router import router as narratives_router
from app.visual_validation.router import router as annotations_router

api_router = APIRouter()

api_router.include_router(concepts_router)
api_router.include_router(market_data_router)
api_router.include_router(narratives_router)
api_router.include_router(annotations_router)
api_router.include_router(feedback_router)


@api_router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
