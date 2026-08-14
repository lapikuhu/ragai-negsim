import pytest

from app.schemas.simulations_schemas import (
    SimulationRetrievalCompatiblePair,
    SimulationRetrievalIndexOption,
    SimulationRetrievalOptionsResponse,
)
from app.web.routes import simulations_route


def _response() -> SimulationRetrievalOptionsResponse:
    return SimulationRetrievalOptionsResponse(
        mode="hybrid",
        dense_indices=[SimulationRetrievalIndexOption(id=101, name="Dense")],
        bm25_indices=[SimulationRetrievalIndexOption(id=202, name="BM25")],
        compatible_pairs=[
            SimulationRetrievalCompatiblePair(
                corpus_index_id=101,
                bm25_index_id=202,
            )
        ],
    )


def test_retrieval_options_route_is_typed_in_openapi(test_app):
    operation = test_app.openapi()["paths"]["/simulations/retrieval-options"]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SimulationRetrievalOptionsResponse"
    }


def test_retrieval_options_route_allows_an_authenticated_student(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
):
    expected = _response()
    captured = {}

    async def fake_service(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(
        simulations_route.simulation_retrieval_options_service,
        "get_simulation_retrieval_options_srvc",
        fake_service,
    )
    override_current_user(username="student", roles=["student"])
    session = override_session()

    response = api_client.get(
        "/simulations/retrieval-options?corpus_id=44&rag_profile_id=7"
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
    assert captured == {
        "corpus_id": 44,
        "rag_profile_id": 7,
        "session": session,
    }


def test_retrieval_options_route_requires_authentication(api_client, override_session):
    override_session()

    response = api_client.get(
        "/simulations/retrieval-options?corpus_id=44&rag_profile_id=7"
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("message", "expected_status"),
    [
        ("Corpus not found", 404),
        ("RAG profile not found", 404),
        ("Retrieval options require a CRAG profile", 409),
    ],
)
def test_retrieval_options_route_maps_service_errors(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    message,
    expected_status,
):
    async def fake_service(**kwargs):
        raise ValueError(message)

    monkeypatch.setattr(
        simulations_route.simulation_retrieval_options_service,
        "get_simulation_retrieval_options_srvc",
        fake_service,
    )
    override_current_user(username="student", roles=["student"])
    override_session()

    response = api_client.get(
        "/simulations/retrieval-options?corpus_id=44&rag_profile_id=7"
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": message}
