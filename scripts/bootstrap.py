from pathlib import Path
import sys


def ensure_project_root_on_path(script_path: str | Path) -> None:
    """
    Ensure direct script execution can import project packages from the repo root.
    """
    project_root = Path(script_path).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
