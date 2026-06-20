import pytest

import scripts.flushdb_and_seed as flushdb_and_seed


@pytest.mark.asyncio
async def test_main_flushes_database_before_seeding(monkeypatch):
    calls: list[str] = []

    async def fake_flush_db():
        calls.append("flush")

    async def fake_seed_main():
        calls.append("seed")

    monkeypatch.setattr(flushdb_and_seed, "flush_db", fake_flush_db)
    monkeypatch.setattr(flushdb_and_seed.seeder, "main", fake_seed_main)

    await flushdb_and_seed.main()

    assert calls == ["flush", "seed"]
