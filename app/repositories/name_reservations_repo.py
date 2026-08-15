import hashlib

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession


async def lock_name_reservation(
    scope: str,
    name: str,
    session: AsyncSession,
) -> None:
    """
    Serialize a PostgreSQL check-and-create reservation transaction.
    Railguard against concurrent transactions attempting to insert the
    same name.

    Args:
        scope: The scope of the name reservation.
        name: The name to reserve.
        session: The database session.
    Returns:
        None.
    """
    get_bind = getattr(session, "get_bind", None)
    if get_bind is None:
        return # gracefully fail if session does not support get_bind
    bind = get_bind()
    if bind.dialect.name != "postgresql":
        return # gracefully fail if not using PostgreSQL
    digest = hashlib.sha256(f"{scope}\0{name}".encode("utf-8")).digest()
    key = int.from_bytes(digest[:8], byteorder="big", signed=True)
    await session.exec(
        text("SELECT pg_advisory_xact_lock(:key)").bindparams(key=key)
    )
