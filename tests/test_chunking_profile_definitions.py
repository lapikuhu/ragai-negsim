from app.airag.chunking.definitions import (
    get_chunker_definition,
    list_chunker_definitions,
    normalize_chunking_profile_config,
)


def test_list_chunker_definitions_exposes_supported_strategies():
    definitions = list_chunker_definitions()
    strategies = {definition.strategy for definition in definitions}

    assert strategies == {"recursive", "semantic", "hybrid"}


def test_hybrid_definition_exposes_combined_fields_and_defaults():
    definition = get_chunker_definition("hybrid")
    field_names = [field.name for field in definition.fields]

    assert definition.supports_ingestion is True
    assert field_names == [
        "breakpoint_threshold_type",
        "breakpoint_threshold_amount",
        "buffer_size",
        "chunk_size",
        "chunk_overlap",
        "separators",
    ]

    normalized = normalize_chunking_profile_config("hybrid", {})

    assert normalized == {
        "breakpoint_threshold_type": "percentile",
        "breakpoint_threshold_amount": 90,
        "buffer_size": 1,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "separators": ["\n\n", "\n", " ", ""],
    }


def test_semantic_definition_supports_ingestion():
    definition = get_chunker_definition("semantic")

    assert definition.supports_ingestion is True


def test_recursive_definition_exposes_immutable_separator_default():
    definition = get_chunker_definition("recursive")
    separators_field = next(field for field in definition.fields if field.name == "separators")

    assert separators_field.default == ("\n\n", "\n", " ", "")
    assert isinstance(separators_field.default, tuple)


def test_recursive_config_normalization_applies_defaults():
    normalized = normalize_chunking_profile_config(
        "recursive",
        {"chunk_size": 512},
    )

    assert normalized == {
        "chunk_size": 512,
        "chunk_overlap": 200,
        "separators": ["\n\n", "\n", " ", ""],
    }


def test_recursive_config_normalization_returns_isolated_default_separator_lists():
    first = normalize_chunking_profile_config("recursive", {"chunk_size": 512})
    second = normalize_chunking_profile_config("recursive", {"chunk_size": 512})

    first["separators"].append("...")

    assert second["separators"] == ["\n\n", "\n", " ", ""]


def test_recursive_config_normalization_rejects_bool_for_int_fields():
    try:
        normalize_chunking_profile_config("recursive", {"chunk_size": True})
    except ValueError as exc:
        assert "chunk_size must be an integer" in str(exc)
    else:
        raise AssertionError("Expected ValueError for bool int field input")


def test_recursive_config_normalization_rejects_non_dict_config_values():
    for invalid_config in ([], "", 0):
        try:
            normalize_chunking_profile_config("recursive", invalid_config)
        except ValueError as exc:
            assert "config must be a dictionary or none" in str(exc).lower()
        else:
            raise AssertionError("Expected ValueError for non-dict config input")


def test_semantic_config_normalization_rejects_unknown_keys():
    try:
        normalize_chunking_profile_config("semantic", {"unknown": 1})
    except ValueError as exc:
        assert "unknown config fields" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for invalid semantic config")


def test_get_chunker_definition_rejects_unknown_strategy():
    try:
        get_chunker_definition("graph")
    except ValueError as exc:
        assert "unsupported chunking strategy" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for unknown strategy")
