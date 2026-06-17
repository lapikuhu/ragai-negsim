from typing import Literal

from sqlmodel import Field, SQLModel


LLMProvider = Literal["openai", "ollama"]


class LLMModelCatalogItem(SQLModel):
    name: str = Field(min_length=1)
    size_gib: float | None = None


class LLMProviderCatalog(SQLModel):
    provider: LLMProvider
    models: list[LLMModelCatalogItem] = Field(default_factory=list)
    error: str | None = None


class LLMModelCatalogResponse(SQLModel):
    providers: list[LLMProviderCatalog] = Field(default_factory=list)
    gpu_memory_gib: float | None = None
