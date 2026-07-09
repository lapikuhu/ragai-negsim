from pathlib import Path
import sys

from scripts.bootstrap import ensure_project_root_on_path


def test_ensure_project_root_on_path_prepends_repo_root(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "seeder.py"
    original_path = ["C:\\temp\\site-packages", str(script_path.parent)]

    monkeypatch.setattr("sys.path", original_path.copy())

    ensure_project_root_on_path(script_path)

    assert sys.path[0] == str(repo_root)
    assert sys.path.count(str(repo_root)) == 1
