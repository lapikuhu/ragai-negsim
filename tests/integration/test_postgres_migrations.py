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
            assert script.get_heads() == ["e7a8b9c0d1e2"]
            assert current_revision == "e7a8b9c0d1e2"
            assert script.get_revision(current_revision).down_revision == "d6f7a8b9c0d1"

            table_names = set(inspector.get_table_names())
            assert {
                "role",
                "user",
                "userrolelink",
                "simulation",
                "simulationevidenceledger",
                "corpusindex",
                "knowledgegraphindex",
                "corpusbm25index",
                "corpusbm25buildjob",
                "corpuschunkset",
                "corpuschunksetdocumentchunklink",
            } <= table_names

            chunk_set_columns = {
                column["name"]: column
                for column in inspector.get_columns("corpuschunkset")
            }
            assert {
                "corpus_id",
                "name",
                "chunking_profile_id",
                "chunking_profile_name",
                "chunking_strategy",
                "chunking_config",
                "revision",
                "document_chunk_ids_checksum",
            } <= chunk_set_columns.keys()
            assert any(
                constraint["name"] == "uq_corpus_chunk_set_corpus_name"
                and constraint["column_names"] == ["corpus_id", "name"]
                for constraint in inspector.get_unique_constraints("corpuschunkset")
            )

            for artifact_table in ("corpusindex", "corpusbm25index"):
                artifact_columns = {
                    column["name"]: column
                    for column in inspector.get_columns(artifact_table)
                }
                assert {
                    "corpus_chunk_set_id",
                    "corpus_chunk_set_revision",
                    "corpus_chunk_set_checksum",
                } <= artifact_columns.keys()
                assert artifact_columns["corpus_chunk_set_id"]["nullable"] is False
                assert artifact_columns["corpus_chunk_set_revision"]["nullable"] is False
                assert artifact_columns["corpus_chunk_set_checksum"]["nullable"] is False

            bm25_job_columns = {
                column["name"]: column
                for column in inspector.get_columns("corpusbm25buildjob")
            }
            assert {
                "corpus_chunk_set_id",
                "corpus_chunk_set_revision",
                "corpus_chunk_set_checksum",
            } <= bm25_job_columns.keys()
            assert bm25_job_columns["corpus_chunk_set_id"]["nullable"] is True
            assert bm25_job_columns["corpus_chunk_set_revision"]["nullable"] is False
            assert bm25_job_columns["corpus_chunk_set_checksum"]["nullable"] is False

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

            full_pipe_columns = {
                column["name"]: column
                for column in inspector.get_columns("fullcorpusindexpipejob")
            }
            assert {
                "build_bm25",
                "requested_bm25_index_name",
                "requested_by_user_id",
                "bm25_build_job_id",
                "requested_chunk_set_name",
                "corpus_chunk_set_id",
            } <= full_pipe_columns.keys()
            assert full_pipe_columns["build_bm25"]["nullable"] is False
            assert full_pipe_columns["build_bm25"]["default"] in {
                "false",
                "false::boolean",
            }
            assert full_pipe_columns["requested_chunk_set_name"]["nullable"] is False
            assert full_pipe_columns["corpus_chunk_set_id"]["nullable"] is True

            def foreign_key_ondelete(table_name, constrained_column):
                foreign_key = next(
                    item
                    for item in inspector.get_foreign_keys(table_name)
                    if item["constrained_columns"] == [constrained_column]
                )
                return (
                    foreign_key["referred_table"],
                    foreign_key.get("options", {}).get("ondelete"),
                )

            assert foreign_key_ondelete("corpuschunkset", "corpus_id") == (
                "corpus",
                "CASCADE",
            )
            assert foreign_key_ondelete("corpuschunkset", "chunking_profile_id") == (
                "chunkingprofile",
                "SET NULL",
            )
            assert foreign_key_ondelete(
                "corpuschunksetdocumentchunklink", "corpus_chunk_set_id"
            ) == ("corpuschunkset", "CASCADE")
            assert foreign_key_ondelete(
                "corpuschunksetdocumentchunklink", "document_chunk_id"
            ) == ("documentchunk", "RESTRICT")
            assert foreign_key_ondelete("corpusindex", "corpus_chunk_set_id") == (
                "corpuschunkset",
                "RESTRICT",
            )
            assert foreign_key_ondelete("corpusbm25index", "corpus_chunk_set_id") == (
                "corpuschunkset",
                "RESTRICT",
            )
            assert foreign_key_ondelete(
                "corpusbm25buildjob", "corpus_chunk_set_id"
            ) == ("corpuschunkset", "SET NULL")
            assert foreign_key_ondelete(
                "fullcorpusindexpipejob", "corpus_chunk_set_id"
            ) == ("corpuschunkset", "SET NULL")

            full_pipe_foreign_keys = inspector.get_foreign_keys(
                "fullcorpusindexpipejob"
            )
            full_pipe_fk_targets = {
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in full_pipe_foreign_keys
            }
            assert (("requested_by_user_id",), "user", ("id",)) in full_pipe_fk_targets
            assert (
                ("bm25_build_job_id",),
                "corpusbm25buildjob",
                ("id",),
            ) in full_pipe_fk_targets

            foreign_keys = inspector.get_foreign_keys("userrolelink")
            constrained_columns = {
                column
                for foreign_key in foreign_keys
                for column in foreign_key["constrained_columns"]
            }
            assert {"user_id", "role_id"} <= constrained_columns
    finally:
        engine.dispose()
