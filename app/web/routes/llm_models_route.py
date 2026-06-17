from fastapi import APIRouter

from app.core.dependencies import CurrentUserDep
from app.schemas.llm_models_schemas import LLMModelCatalogResponse
from app.services.llm_models_service import list_llm_model_catalog

# Instantiate the API router for LLM models with a prefix and tags for documentation.
router = APIRouter(prefix="/llm-models", tags=["llm-models"])

#### ----------------------- LLM MODEL CATALOG --------------------- ###
@router.get("/catalog", 
            response_model=LLMModelCatalogResponse)
async def get_llm_model_catalog(_current_user: CurrentUserDep) -> LLMModelCatalogResponse:
    """
    Retrieve the catalog of available LLM models.
    Args:
        _current_user: The current user dependency.
    Returns:
        LLMModelCatalogResponse: The response containing the LLM model catalog.
    """
    return list_llm_model_catalog()
