def test_list_rag_profile_definitions_route_returns_crag_definition(
    api_client,
    override_current_user,
):
    override_current_user(username="admin", roles=["admin"])

    response = api_client.get("/rag-profiles/definitions")

    assert response.status_code == 200
    strategies = {item["strategy"] for item in response.json()}
    assert strategies == {"crag", "graphrag"}


def test_rag_profile_definition_json_exposes_numeric_float_bounds(
    api_client,
    override_current_user,
):
    override_current_user(username="admin", roles=["admin"])

    response = api_client.get("/rag-profiles/definitions")

    assert response.status_code == 200
    crag = next(item for item in response.json() if item["strategy"] == "crag")
    weight = next(field for field in crag["fields"] if field["name"] == "bm25_weight")
    assert weight == {
        "name": "bm25_weight",
        "kind": "float",
        "label": "BM25 weight",
        "required": True,
        "default": 0.0,
        "minimum": 0.0,
        "maximum": 1.0,
        "help_text": (
            "Use 0 for dense-only retrieval, 1 for BM25-only retrieval, or an "
            "intermediate value for hybrid retrieval."
        ),
        "options": [],
    }

    openapi = api_client.get("/openapi.json")
    assert openapi.status_code == 200
    field_schema = openapi.json()["components"]["schemas"][
        "RagProfileFieldDefinitionRead"
    ]["properties"]
    assert field_schema["kind"]["enum"] == ["int", "float", "enum"]
