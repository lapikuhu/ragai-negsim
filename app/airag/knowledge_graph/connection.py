from urllib.parse import urlparse


DEFAULT_NEO4J_DATABASE = "neo4j"


def resolve_neo4j_uri(uri: str) -> str:
    """
    Convert local routing URIs to direct Bolt URIs for standalone Neo4j.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "neo4j":
        return uri
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return uri
    return parsed._replace(scheme="bolt").geturl()


def describe_neo4j_error(exc: Exception, uri: str) -> str:
    """
    Expand common Neo4j routing failures with a local-setup hint.
    """
    detail = str(exc)
    parsed = urlparse(uri)
    if (
        "Unable to retrieve routing information" in detail
        and parsed.scheme == "neo4j"
        and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        suggested_uri = resolve_neo4j_uri(uri)
        return (
            f"{detail}. Local standalone Neo4j usually requires a direct "
            f"connection URI. Try `NEO4J_URI={suggested_uri}`."
        )
    return detail


def resolve_neo4j_database(database: str | None) -> str:
    """
    Normalize the configured Neo4j database name.
    """
    value = (database or "").strip()
    return value or DEFAULT_NEO4J_DATABASE
