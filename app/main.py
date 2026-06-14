from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.db import startup_seed
from app.core.config import settings
from app.web.routes.chunking_profiles_route import router as chunking_profiles_router
from app.web.routes.counterpart_personas_route import router as counterpart_personas_router
from app.web.routes.corpus_indices_route import router as corpus_indices_router
from app.web.routes.corpus_route import router as corpus_router
from app.web.routes.embeddings_route import router as embeddings_router
from app.web.routes.indexing_jobs_route import router as indexing_jobs_router
from app.web.routes.prompts_route import router as prompts_router
from app.web.routes.rag_profiles_route import router as rag_profiles_router
from app.web.routes.raw_documents_route import router as raw_documents_router
from app.web.routes.scenarios_route import router as scenarios_router
from app.web.routes.sessions_route import router as sessions_router
from app.web.routes.simulations_route import router as simulations_router
from app.web.routes.users_route import router as users_router
from app.web.routes.vector_stores_route import router as vector_stores_router

from app.core.logging import configure_logging
from app.middleware.logging import RequestLoggingMiddleware

@asynccontextmanager
# async context manager for lifespan allows us to run async code during startup and shutdown
async def lifespan(app: FastAPI):
    await startup_seed() # setup: seed startup data after Alembic migrations
    from app.services.indexing_jobs_service import fail_interrupted_indexing_jobs_srvc

    await fail_interrupted_indexing_jobs_srvc()
    
    print("Database setup complete. [OK]")

    yield # execution pauses here and the app starts accepting requests

    print("Shutting down application... [OK]")

# Configure the logger before the app starts 
# Handles only HTTP request logging, not the root logger.
configure_logging()

# Instantiate the FastAPI application with the lifespan handler
app = FastAPI(title="Negotiation Simulator", lifespan=lifespan, tags=["app"])

# Add middleware
# CORS allows cross-origin requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# HTTP requests logging
app.add_middleware(RequestLoggingMiddleware)

# Register the routers
app.include_router(users_router)
app.include_router(chunking_profiles_router)
app.include_router(corpus_indices_router)
app.include_router(corpus_router)
app.include_router(embeddings_router)
app.include_router(indexing_jobs_router)
app.include_router(prompts_router)
app.include_router(rag_profiles_router)
app.include_router(raw_documents_router)
app.include_router(scenarios_router)
app.include_router(counterpart_personas_router)
app.include_router(simulations_router)
app.include_router(sessions_router)
app.include_router(vector_stores_router)
