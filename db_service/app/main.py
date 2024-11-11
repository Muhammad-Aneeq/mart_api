import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import Depends, FastAPI, HTTPException
from alembic.config import Config

# from app.kafka_consumer import consume_events
from alembic import command
import concurrent.futures
from app.routers import (user_router)
from app.config import init_db
# from app.routers import (
#     user_router,
#     product_router,
#     category_router,
#     brand_router,
#     order_router,
#     payment_router,
#     customer_router
# )


# Database initialization function
async def run_db_initialization():
    """
    This function ensures that the database tables are created at the startup
    by calling the `init_db` function.
    """
    await asyncio.to_thread(init_db)  # Run init_db in a separate thread to avoid blocking


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print("starting lifespan process")
    
    # Ensure the DB tables are created on app startup
    await run_db_initialization()

    # The `yield` indicates the end of startup logic, and the app runs hereafter
    yield


app = FastAPI(lifespan=lifespan, title="Hello World db service API")


"""
This will include all the routes defined in router directory
"""
app.include_router(user_router.router)



@app.get("/health")
async def health():
    return {"status": "ok"}


# Test endpoint to manually trigger the database initialization
@app.get("/dbup")
async def dbup():
    try:
        # Initialize DB tables (if they don't exist)
        await run_db_initialization()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
