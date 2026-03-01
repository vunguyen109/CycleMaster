from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models.db import init_db
from app.api.routes import router
from app.utils.logging import setup_logging
from app.scheduler.scheduler import start_scheduler


setup_logging()
init_db()

app = FastAPI(title='CycleMaster')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
app.include_router(router)

scheduler = None


@app.on_event('startup')
def on_startup():
    global scheduler
    scheduler = start_scheduler()


@app.on_event('shutdown')
def on_shutdown():
    global scheduler
    if scheduler:
        scheduler.shutdown()
