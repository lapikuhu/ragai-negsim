def test_list_chunker_definitions_route_returns_supported_strategies(
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    override_current_user(username="admin", roles=["admin"])
    override_session()
    allow_roles("admin")

    response = api_client.get("/chunking-profiles/definitions")

    assert response.status_code == 200
    strategies = {item["strategy"] for item in response.json()}
    assert strategies == {"recursive", "semantic", "hybrid"}
