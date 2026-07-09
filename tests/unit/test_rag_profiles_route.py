def test_list_rag_profile_definitions_route_returns_crag_definition(
    api_client,
    override_current_user,
):
    override_current_user(username="admin", roles=["admin"])

    response = api_client.get("/rag-profiles/definitions")

    assert response.status_code == 200
    strategies = {item["strategy"] for item in response.json()}
    assert strategies == {"crag", "graphrag"}
