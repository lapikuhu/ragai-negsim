from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.db import create_db_and_tables

@asynccontextmanager
# async context manager for lifespan allows us to run async code during startup and shutdown
async def lifespan(app: FastAPI):
    await create_db_and_tables() # setup: seed startup data after Alembic migrations
    
    print("Database setup complete. [OK]")

    yield # execution pauses here and the app starts accepting requests

    print("Shutting down application... [OK]")

# Instantiate the FastAPI application with the lifespan handler
app = FastAPI(title="Negotiation Simulator", lifespan=lifespan, tags=["app"])

# Register the routers
