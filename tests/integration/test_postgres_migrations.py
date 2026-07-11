from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.alembic
def test_alembic_migrations_apply_to_postgres(migrated_postgres_db):
    """
    Test that Alembic migrations have been applied correctly to the 
    PostgreSQL database.
    """
    engine = create_engine(migrated_postgres_db["sync_url"], pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            current_revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            inspector = inspect(connection)

            alembic_cfg = Config("alembic.ini")
            script = ScriptDirectory.from_config(alembic_cfg)

            assert current_revision == script.get_current_head()

            table_names = set(inspector.get_table_names())
            assert {
                "role",
                "user",
                "userrolelink",
                "simulation",
                "simulationevidenceledger",
                "corpusindex",
                "knowledgegraphindex",
            } <= table_names

            simulation_columns = {
                column["name"]: column for column in inspector.get_columns("simulation")
            }
            assert "negotiation_state" in simulation_columns
            assert "messages" in simulation_columns
            assert "created_at" in simulation_columns
            assert simulation_columns["created_at"]["type"].timezone is True

            ledger_columns = {
                column["name"]: column
                for column in inspector.get_columns("simulationevidenceledger")
            }
            assert "pipeline" in ledger_columns
            assert "sources" in ledger_columns
            assert "created_at" in ledger_columns
            assert ledger_columns["created_at"]["type"].timezone is True

            foreign_keys = inspector.get_foreign_keys("userrolelink")
            constrained_columns = {
                column
                for foreign_key in foreign_keys
                for column in foreign_key["constrained_columns"]
            }
            assert {"user_id", "role_id"} <= constrained_columns
    finally:
        engine.dispose()