import pytest

from app.web.routes import chunking_profiles_route


@pytest.mark.asyncio
async def test_list_chunker_definitions_route_returns_supported_strategies():
    definitions = await chunking_profiles_route.list_chunker_definitions(object())
    strategies = {item.strategy for item in definitions}
    assert strategies == {"recursive", "semantic"}
