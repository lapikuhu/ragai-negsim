def _persisted_id(value: int | None, label: str) -> int:
    """
    Utility function to ensure that a given value is not None, indicating that
    it has been persisted. If the value is None, a ValueError is raised with a
    message indicating which label is missing.
    Args:
    value (int | None): The value to check for persistence.
    label (str): A descriptive label for the value being checked, used in the
    error message if the value is not persisted.
    Returns:
        int: The original value if it is not None, indicating it has been 
            persisted.
    Raises:
        ValueError: If the value is None, indicating it has not been persisted.
    """
    if value is None:
        raise ValueError(f"{label} must be persisted before ingestion")
    return value