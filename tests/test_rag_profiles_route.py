import pytest

from app.web.routes import rag_profiles_route


@pytest.mark.asyncio
async def test_list_rag_profile_definitions_route_returns_crag_definition():
    definitions = await rag_profiles_route.list_rag_profile_definitions(object())
    strategies = {item.strategy for item in definitions}
    assert strategies == {"crag", "graphrag"}
