import subprocess
import sys
from pathlib import Path


def test_importing_models_registers_all_relationship_targets():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import app.models; "
                "from sqlmodel import SQLModel; "
                "from sqlalchemy.orm import configure_mappers; "
                "expected = {'user', 'prompt', 'knowledgegraphindex', "
                "'knowledgegraphbuildjob'}; "
                "missing = expected - set(SQLModel.metadata.tables); "
                "assert not missing, f'Missing model tables: {sorted(missing)}'; "
                "configure_mappers()"
            ),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
