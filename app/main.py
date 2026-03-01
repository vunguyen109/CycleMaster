from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.models.db import init_db
from app.api.routes import router
from app.utils.logging import setup_logging
from app.scheduler.scheduler import start_scheduler
import logging

logger = logging.getLogger(__name__)

# Initialize logging and database on module load
setup_logging()
logger.info("Initializing database...")
init_db()
logger.info("Database initialized successfully")

app = FastAPI(title='CycleMaster', version='1.0.0')

# CORS Middleware - Allow all origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

app.include_router(router)

scheduler = None


@app.get('/', tags=['health'])
async def health_check():
    """Health check endpoint for deployment monitoring."""
    return JSONResponse(
        status_code=200,
        content={
            'status': 'healthy',
            'service': 'CycleMaster',
            'version': '1.0.0'
        }
    )


@app.on_event('startup')
def on_startup():
    """Start scheduler on app startup."""
    global scheduler
    try:
        logger.info("Starting scheduler...")
        scheduler = start_scheduler()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        # Don't crash the app if scheduler fails


@app.on_event('shutdown')
def on_shutdown():
    """Shutdown scheduler on app shutdown."""
    global scheduler
    if scheduler:
        try:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shutdown successfully")
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {e}", exc_info=True)
