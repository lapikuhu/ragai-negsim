from fastapi import APIRouter

from app.core.dependencies import AdminDep
from app.airag.embeddings.embeddings import list_supported_embedding_models
from app.schemas.embeddings_schemas import EmbeddingModelRead


router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.get("/models", response_model=list[EmbeddingModelRead], status_code=200)
async def list_embedding_models(
    _admin: AdminDep,
) -> list[EmbeddingModelRead]:
    """
    List all supported embedding models endpoint.
    Args:
        _admin: The current admin user performing the operation (for authorization).
    Returns:
        A list of supported embedding models with their details.
    """
    return [
        EmbeddingModelRead(**model_info)
        for model_info in list_supported_embedding_models()
    ]
