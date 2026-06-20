from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.scenarios_schemas import (
    ScenarioAuthoringReadWithIds,
    ScenarioContextGenerateRequest,
    ScenarioCopyRequest,
    ScenarioCreateRequest,
    ScenarioPublicReadWithIds,
    ScenarioUpdateRequest,
)
from app.services import scenarios_service


def _user(user_id=1):
    return SimpleNamespace(id=user_id, username=f"user-{user_id}")


def _scenario(scenario_id=10, created_by_user_id=1, last_edit_by_user_id=None):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=scenario_id,
        name=f"scenario-{scenario_id}",
        description="AUTHORING-DESCRIPTION",
        public_context={"public_fact": f"PUBLIC-{scenario_id}"},
        side_a_private_context={"reservation": f"SIDE-A-SECRET-{scenario_id}"},
        side_b_private_context={"reservation": f"SIDE-B-SECRET-{scenario_id}"},
        side_a_summary=f"Side A summary {scenario_id}",
        side_b_summary=f"Side B summary {scenario_id}",
        created_by_user_id=created_by_user_id,
        last_edit_by_user_id=last_edit_by_user_id,
        created_at=now,
        last_updated=now,
        model_dump=lambda: {
            "id": scenario_id,
            "name": f"scenario-{scenario_id}",
            "description": "AUTHORING-DESCRIPTION",
            "public_context": {"public_fact": f"PUBLIC-{scenario_id}"},
            "side_a_private_context": {"reservation": f"SIDE-A-SECRET-{scenario_id}"},
            "side_b_private_context": {"reservation": f"SIDE-B-SECRET-{scenario_id}"},
            "side_a_summary": f"Side A summary {scenario_id}",
            "side_b_summary": f"Side B summary {scenario_id}",
            "created_by_user_id": created_by_user_id,
            "last_edit_by_user_id": last_edit_by_user_id,
            "created_at": now,
            "last_updated": now,
        },
    )


def test_public_scenario_schema_excludes_authoring_and_private_fields():
    public = ScenarioPublicReadWithIds(
        id=10,
        name="Late checkout",
        description="Practice checkout negotiation.",
        public_context={"issue": "checkout time and fee"},
        created_by_user_id=1,
        last_edit_by_user_id=None,
        created_at=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
        simulation_ids=[],
    )

    payload = public.model_dump()

    assert payload["description"] == "Practice checkout negotiation."
    assert "side_a_private_context" not in payload
    assert "side_b_private_context" not in payload
    assert "side_a_summary" not in payload
    assert "side_b_summary" not in payload


@pytest.mark.asyncio
async def test_create_scenario_stamps_current_user(monkeypatch):
    captured = []
    created = _scenario(created_by_user_id=7)

    async def fake_create_scenario(scenario_in, session):
        captured.append(scenario_in)
        return created

    async def fake_to_read_with_ids(scenario, session):
        return ScenarioAuthoringReadWithIds(**scenario.model_dump(), simulation_ids=[])

    monkeypatch.setattr(scenarios_service.scenarios_repo, "create_scenario", fake_create_scenario)
    monkeypatch.setattr(
        scenarios_service.scenarios_repo,
        "to_scenario_authoring_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await scenarios_service.create_scenario_srvc(
        ScenarioCreateRequest(
            name="Salary negotiation",
            description="Practice pay discussions",
            side_a_summary="You are the candidate.",
            side_b_summary="You are the recruiter.",
        ),
        object(),
        _user(7),
    )

    assert result.created_by_user_id == 7
    assert captured[0].created_by_user_id == 7
    assert captured[0].name == "Salary negotiation"
    assert captured[0].side_a_summary == "You are the candidate."
    assert captured[0].side_b_summary == "You are the recruiter."


@pytest.mark.asyncio
async def test_update_scenario_stamps_last_editor(monkeypatch):
    captured = []
    updated = _scenario(created_by_user_id=2, last_edit_by_user_id=9)

    async def fake_update_scenario(scenario, scenario_in, session):
        captured.append((scenario, scenario_in))
        return updated

    async def fake_to_read_with_ids(scenario, session):
        return ScenarioAuthoringReadWithIds(**scenario.model_dump(), simulation_ids=[33])

    monkeypatch.setattr(scenarios_service.scenarios_repo, "update_scenario", fake_update_scenario)
    monkeypatch.setattr(
        scenarios_service.scenarios_repo,
        "to_scenario_authoring_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await scenarios_service.update_scenario_srvc(
        _scenario(created_by_user_id=2),
        ScenarioUpdateRequest(name="Updated scenario"),
        object(),
        _user(9),
    )

    assert result.last_edit_by_user_id == 9
    assert result.simulation_ids == [33]
    assert captured[0][1].last_edit_by_user_id == 9
    assert captured[0][1].name == "Updated scenario"


@pytest.mark.asyncio
async def test_update_scenario_accepts_side_summaries(monkeypatch):
    captured = []
    updated = _scenario(created_by_user_id=2, last_edit_by_user_id=9)

    async def fake_update_scenario(scenario, scenario_in, session):
        captured.append(scenario_in)
        return updated

    async def fake_to_read_with_ids(scenario, session):
        return ScenarioAuthoringReadWithIds(**scenario.model_dump(), simulation_ids=[])

    monkeypatch.setattr(scenarios_service.scenarios_repo, "update_scenario", fake_update_scenario)
    monkeypatch.setattr(
        scenarios_service.scenarios_repo,
        "to_scenario_authoring_read_with_ids",
        fake_to_read_with_ids,
    )

    await scenarios_service.update_scenario_srvc(
        _scenario(created_by_user_id=2),
        ScenarioUpdateRequest(
            side_a_summary="Updated side A summary",
            side_b_summary="Updated side B summary",
        ),
        object(),
        _user(9),
    )

    assert captured[0].side_a_summary == "Updated side A summary"
    assert captured[0].side_b_summary == "Updated side B summary"


@pytest.mark.asyncio
async def test_copy_scenario_stamps_current_user(monkeypatch):
    captured = []
    copied = _scenario(scenario_id=22, created_by_user_id=11)

    async def fake_copy_scenario(source_scenario, copy_in, session):
        captured.append((source_scenario, copy_in))
        return copied

    async def fake_to_read_with_ids(scenario, session):
        return ScenarioAuthoringReadWithIds(**scenario.model_dump(), simulation_ids=[])

    monkeypatch.setattr(scenarios_service.scenarios_repo, "copy_scenario", fake_copy_scenario)
    monkeypatch.setattr(
        scenarios_service.scenarios_repo,
        "to_scenario_authoring_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await scenarios_service.copy_scenario_srvc(
        _scenario(),
        ScenarioCopyRequest(name="Copied scenario"),
        object(),
        _user(11),
    )

    assert result.created_by_user_id == 11
    assert captured[0][1].created_by_user_id == 11
    assert captured[0][1].name == "Copied scenario"


@pytest.mark.asyncio
async def test_list_scenarios_passes_filters_and_converts(monkeypatch):
    captured = []
    scenarios = [_scenario(1), _scenario(2)]

    async def fake_list_scenarios(
        session,
        skip=0,
        limit=20,
        created_by_user_id=None,
        name_contains=None,
        used=None,
    ):
        captured.append((skip, limit, created_by_user_id, name_contains, used))
        return scenarios

    async def fake_to_public(scenario, session):
        return ScenarioPublicReadWithIds(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            public_context=scenario.public_context,
            created_by_user_id=scenario.created_by_user_id,
            last_edit_by_user_id=scenario.last_edit_by_user_id,
            created_at=scenario.created_at,
            last_updated=scenario.last_updated,
            simulation_ids=[scenario.id + 100],
        )

    monkeypatch.setattr(scenarios_service.scenarios_repo, "list_scenarios", fake_list_scenarios)
    monkeypatch.setattr(
        scenarios_service.scenarios_repo,
        "to_scenario_public_read_with_ids",
        fake_to_public,
    )

    result = await scenarios_service.list_scenarios_srvc(
        object(),
        skip=5,
        limit=10,
        created_by_user_id=3,
        name_contains="salary",
        used=False,
    )

    assert captured == [(5, 10, 3, "salary", False)]
    assert [scenario.simulation_ids for scenario in result] == [[101], [102]]
    assert result[0].public_context["public_fact"] == "PUBLIC-1"
    assert result[0].description == "AUTHORING-DESCRIPTION"


@pytest.mark.asyncio
async def test_get_scenario_returns_public_view(monkeypatch):
    scenario = _scenario(10)

    async def fake_to_public(scenario_obj, session):
        return ScenarioPublicReadWithIds(
            id=scenario_obj.id,
            name=scenario_obj.name,
            description=scenario_obj.description,
            public_context=scenario_obj.public_context,
            created_by_user_id=scenario_obj.created_by_user_id,
            last_edit_by_user_id=scenario_obj.last_edit_by_user_id,
            created_at=scenario_obj.created_at,
            last_updated=scenario_obj.last_updated,
            simulation_ids=[],
        )

    monkeypatch.setattr(
        scenarios_service.scenarios_repo,
        "to_scenario_public_read_with_ids",
        fake_to_public,
    )

    result = await scenarios_service.get_scenario_srvc(scenario, object())

    assert result.public_context["public_fact"] == "PUBLIC-10"
    assert result.description == "AUTHORING-DESCRIPTION"
    assert "side_a_private_context" not in result.model_dump()
    assert "side_a_summary" not in result.model_dump()
    assert "side_b_summary" not in result.model_dump()


@pytest.mark.asyncio
async def test_delete_scenario_propagates_repo_guard(monkeypatch):
    async def fake_delete_scenario(scenario, session):
        raise ValueError("Cannot modify scenario that has been used in a simulation")

    monkeypatch.setattr(scenarios_service.scenarios_repo, "delete_scenario", fake_delete_scenario)

    with pytest.raises(ValueError, match="used in a simulation"):
        await scenarios_service.delete_scenario_srvc(_scenario(), object())


@pytest.mark.asyncio
async def test_generate_scenario_context_returns_structured_preview():
    calls = []

    class FakeStructuredModel:
        def __init__(self, schema_name):
            self.schema_name = schema_name

        def invoke(self, payload):
            calls.append((self.schema_name, payload))
            if self.schema_name == "ScenarioContextGenerationModel":
                assert "Hotel late checkout" in payload
                return SimpleNamespace(
                    public_context={"issue": "late checkout"},
                    side_a_private_context={"goal": "avoid paying a fee"},
                    side_b_private_context={"goal": "protect policy"},
                )
            assert "avoid paying a fee" in payload
            assert "protect policy" in payload
            return SimpleNamespace(
                side_a_summary="You are trying to avoid a late checkout fee.",
                side_b_summary="You are trying to protect hotel policy.",
            )

    class FakeModel:
        def with_structured_output(self, schema, **kwargs):
            assert kwargs == {"method": "function_calling"}
            return FakeStructuredModel(schema.__name__)

    result = await scenarios_service.generate_scenario_context_srvc(
        ScenarioContextGenerateRequest(
            name="Hotel late checkout",
            description="A guest negotiates with a front desk manager.",
        ),
        FakeModel(),
    )

    assert result.public_context["issue"] == "late checkout"
    assert result.side_a_private_context["goal"] == "avoid paying a fee"
    assert result.side_b_private_context["goal"] == "protect policy"
    assert result.side_a_summary == "You are trying to avoid a late checkout fee."
    assert result.side_b_summary == "You are trying to protect hotel policy."
    assert [call[0] for call in calls] == [
        "ScenarioContextGenerationModel",
        "ScenarioSummaryGenerationModel",
    ]


@pytest.mark.asyncio
async def test_generate_scenario_context_raises_value_error_on_model_failure():
    class FakeStructuredModel:
        def invoke(self, payload):
            raise RuntimeError("boom")

    class FakeModel:
        def with_structured_output(self, schema):
            return FakeStructuredModel()

    with pytest.raises(ValueError, match="Unable to generate scenario context"):
        await scenarios_service.generate_scenario_context_srvc(
            ScenarioContextGenerateRequest(
                name="Salary negotiation",
                description="Candidate and recruiter discuss compensation.",
            ),
            FakeModel(),
        )


@pytest.mark.asyncio
async def test_generate_scenario_context_uses_prompt_string_and_function_calling():
    captured = {"schemas": [], "payloads": []}

    class FakeStructuredModel:
        def __init__(self, schema_name):
            self.schema_name = schema_name

        def invoke(self, payload, config=None):
            captured["payloads"].append(payload)
            captured["config"] = config
            if self.schema_name == "ScenarioContextGenerationModel":
                return SimpleNamespace(
                    public_context={"issue": "late checkout"},
                    side_a_private_context={"goal": "avoid paying a fee"},
                    side_b_private_context={"goal": "protect policy"},
                )
            return SimpleNamespace(
                side_a_summary="Side A summary",
                side_b_summary="Side B summary",
            )

    class FakeModel:
        def with_structured_output(self, schema, **kwargs):
            captured["schemas"].append(schema.__name__)
            captured["kwargs"] = kwargs
            return FakeStructuredModel(schema.__name__)

    await scenarios_service.generate_scenario_context_srvc(
        ScenarioContextGenerateRequest(
            name="Hotel late checkout",
            description="A guest negotiates with a front desk manager.",
        ),
        FakeModel(),
        config={
            "tags": ["service:scenario_context"],
            "metadata": {"user_id": "7"},
        },
    )

    assert captured["schemas"] == [
        "ScenarioContextGenerationModel",
        "ScenarioSummaryGenerationModel",
    ]
    assert captured["kwargs"] == {"method": "function_calling"}
    assert all(isinstance(payload, str) for payload in captured["payloads"])
    assert "Split the scenario into exactly three sections" in captured["payloads"][0]
    assert "Generate two free-text side summaries" in captured["payloads"][1]
    assert captured["config"]["tags"] == ["service:scenario_context"]
    assert captured["config"]["metadata"] == {"user_id": "7"}
