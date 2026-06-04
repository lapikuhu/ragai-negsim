from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.db import create_db_and_tables
from web.routes.counterpart_personas_route import router as counterpart_personas_router
from web.routes.corpus_route import router as corpus_router
from web.routes.embeddings_route import router as embeddings_router
from web.routes.raw_documents_route import router as raw_documents_router
from web.routes.scenarios_route import router as scenarios_router
from web.routes.sessions_route import router as sessions_router
from web.routes.simulations_route import router as simulations_router
from web.routes.users_route import router as users_router

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
app.include_router(users_router)
app.include_router(corpus_router)
app.include_router(embeddings_router)
app.include_router(raw_documents_router)
app.include_router(scenarios_router)
app.include_router(counterpart_personas_router)
app.include_router(simulations_router)
app.include_router(sessions_router)
