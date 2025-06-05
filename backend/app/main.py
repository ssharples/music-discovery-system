# backend/app/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

from app.core.config import settings
from app.core.dependencies import get_pipeline_deps, cleanup_dependencies
from app.api import routes, websocket
from app.agents.orchestrator import DiscoveryOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Sentry for error tracking in production
if SENTRY_AVAILABLE and settings.SENTRY_DSN and settings.ENVIRONMENT == "production":
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,
        environment=settings.ENVIRONMENT,
    )
    logger.info("Sentry error tracking initialized")
elif settings.SENTRY_DSN and settings.ENVIRONMENT == "production":
    logger.warning("Sentry SDK not available, error tracking disabled")

# Background task queue
background_tasks_queue = asyncio.Queue()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info(f"Starting Music Discovery System in {settings.ENVIRONMENT} mode...")
    
    # Initialize discovery orchestrator
    app.state.orchestrator = DiscoveryOrchestrator()
    
    # Start background task processor
    app.state.task_processor = asyncio.create_task(process_background_tasks(app))
    
    yield
    
    # Shutdown
    logger.info("Shutting down Music Discovery System...")
    
    # Cancel background tasks
    if hasattr(app.state, 'task_processor'):
        app.state.task_processor.cancel()
        try:
            await app.state.task_processor
        except asyncio.CancelledError:
            pass
    
    # Cleanup dependencies
    await cleanup_dependencies()

async def process_background_tasks(app: FastAPI):
    """Process background discovery tasks"""
    while True:
        try:
            task = await background_tasks_queue.get()
            await app.state.orchestrator.process_discovery_task(task)
            background_tasks_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing background task: {e}")
        await asyncio.sleep(0.1)

# Create FastAPI app
app = FastAPI(
    title="Music Artist Discovery System",
    description="AI-powered music artist discovery and enrichment platform",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.DEBUG
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.router, prefix="/api")
app.include_router(websocket.router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Music Artist Discovery System API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        deps = await get_pipeline_deps()
        health_result = deps.supabase.table("artists").select("count", count="exact").limit(1).execute()
        db_status = "operational" if health_result else "error"
        
        # Test Redis connection
        try:
            await deps.redis_client.ping()
            redis_status = "operational"
        except:
            redis_status = "error"
        
        return {
            "status": "healthy" if db_status == "operational" and redis_status == "operational" else "degraded",
            "services": {
                "api": "operational",
                "database": db_status,
                "redis": redis_status,
                "agents": "operational"
            },
            "environment": settings.ENVIRONMENT
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "environment": settings.ENVIRONMENT
        }

# Add global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}")
    return HTTPException(status_code=500, detail="Internal server error") 