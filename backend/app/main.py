from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.core.redis_client import redis_client
from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize database tables
    try:
        await init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"⚠ Database initialization warning: {e}")
    
    # Connect to Redis
    try:
        await redis_client.connect()
    except Exception as e:
        print(f"⚠ Redis connection warning: {e}")
    
    print(f"✓ Server running on http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"✓ API docs available at http://{settings.API_HOST}:{settings.API_PORT}/docs")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    await redis_client.disconnect()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="National Weather Big Data Analytics Platform for SIH 2026",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )
