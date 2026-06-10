from fastapi import APIRouter

from app.concepts.router import router as concepts_router
from app.displacement.router import router as displacement_router
from app.execution_model.router import router as execution_model_router
from app.feedback.router import router as feedback_router
from app.fvg.router import router as fvg_router
from app.liquidity.router import router as liquidity_router
from app.market_data.router import router as market_data_router
from app.market_structure.router import router as market_structure_router
from app.narrative_engine.router import router as narratives_router
from app.smt.router import router as smt_router
from app.trade_setup.router import router as trade_setup_router
from app.visual_validation.router import router as annotations_router

api_router = APIRouter()

api_router.include_router(concepts_router)
api_router.include_router(market_data_router)
api_router.include_router(market_structure_router)
api_router.include_router(liquidity_router)
api_router.include_router(displacement_router)
api_router.include_router(smt_router)
api_router.include_router(fvg_router)
api_router.include_router(execution_model_router)
api_router.include_router(trade_setup_router)
api_router.include_router(narratives_router)
api_router.include_router(annotations_router)
api_router.include_router(feedback_router)


@api_router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
