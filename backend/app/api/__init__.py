from fastapi import APIRouter
from .health import router as health_router
from .reports import router as reports_router
from .analytics import router as analytics_router
from .events import router as events_router
from .risk import router as risk_router
from .alerts import router as alerts_router

api_router = APIRouter()

# Include all route modules
api_router.include_router(health_router, tags=["health"])
api_router.include_router(reports_router)
api_router.include_router(analytics_router)
api_router.include_router(events_router, prefix="/api/events", tags=["events"])
api_router.include_router(risk_router, prefix="/api/risk", tags=["risk"])
api_router.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])

__all__ = ["api_router"]
