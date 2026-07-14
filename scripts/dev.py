"""
Run the local backend and frontend after preparing a development database.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence


MINIMUM_PYTHON_VERSION = (3, 12)
SHUTDOWN_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class Command:
    args: tuple[str, ...]
    cwd: Path


class CommandFailed(RuntimeError):
    def __init__(self, command: Command, returncode: int) -> None:
        self.command = command
        self.returncode = returncode
        super().__init__(f"Command failed ({returncode}): {' '.join(command.args)}")


def project_root() -> Path:
    """
    Get the repo root directory
    Args:
        None
    Returns:
        Path: The root directory of the project
    """
    return Path(__file__).resolve().parents[1]


def preflight_errors(
    root: Path,
    *,
    python_version: tuple[int, int] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    version = python_version or sys.version_info[:2]
    errors: list[str] = []
    if version < MINIMUM_PYTHON_VERSION:
        errors.append("Python 3.12 or newer is required")
    if not (root / ".env").is_file():
        errors.append(f"Missing environment file: {root / '.env'}")
    for executable in ("uv", "npm"):
        if which(executable) is None:
            errors.append(f"Required executable not found on PATH: {executable}")
    return errors


def setup_commands(root: Path) -> list[Command]:
    """
    Setup commands to prepare the development environment.Covers 
    installing dependencies, running database migrations, and seeding 
    the database.
    Args:
        root (Path): The root directory of the project.

    Returns:
        list[Command]: A list of commands to set up the development environment.
    """
    return [
        Command(("uv", "sync", "--frozen"), root),
        Command(("npm", "ci"), root / "frontend"),
        Command(("uv", "run", "alembic", "upgrade", "head"), root),
        Command(("uv", "run", "python", "scripts/seeder.py"), root),
    ]


def development_commands(root: Path) -> tuple[Command, Command]:
    """
    Setup commands to run the development servers for the backend and 
    frontend.
    """
    return (
        Command(("uv", "run", "uvicorn", "app.main:app", "--reload"), root),
        Command(("npm", "run", "dev"), root / "frontend"),
    )


def run_command(command: Command) -> None:
    """
    Run a command in a subprocess.
    Args:
        command (Command): The command to run.

    Raises:
        CommandFailed: If the command exits with a non-zero status.
    """
    try:
        subprocess.run(command.args, cwd=command.cwd, check=True)
    except subprocess.CalledProcessError as exc:
        raise CommandFailed(command, exc.returncode) from exc


def run_setup(root: Path, runner: Callable[[Command], None] = run_command) -> None:
    """
    Run the setup commands to prepare the development environment.
    Args:
        root (Path): The root directory of the project.
        runner (Callable[[Command], None], optional): The function to 
        run commands. Defaults to run_command.
    """
    for command in setup_commands(root):
        print(f"[setup] {' '.join(command.args)}")
        runner(command)


def _stream_output(label: str, process: subprocess.Popen[str]) -> None:
    """
    Stream the output of a subprocess to the console.
    Args:
        label (str): The label to prefix each line of output with.
        process (subprocess.Popen[str]): The subprocess whose output to stream.
    """
    if process.stdout is None:
        return
    for line in process.stdout:
        print(f"[{label}] {line.rstrip()}")


def _stop_processes(processes: Sequence[subprocess.Popen[str]]) -> None:
    """
    Stop a list of subprocesses, first attempting to terminate them gracefully,
    and then killing them if they do not exit within a timeout.
    Args:
        processes (Sequence[subprocess.Popen[str]]): The list of 
            subprocesses to stop.
    Returns:
        None
    """
    for process in processes:
        if process.poll() is None:
            process.terminate()

    deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
    for process in processes:
        if process.poll() is None:
            remaining = max(0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def run_development(root: Path) -> int:
    """
    Run the development servers for the backend and frontend.
    Args:
        root (Path): The root directory of the project.
    Returns:
        int: The exit code of the development servers.
    """
    commands = development_commands(root)
    processes: list[subprocess.Popen[str]] = []
    try:
        for command in commands:
            print(f"[start] {' '.join(command.args)}")
            processes.append(
                subprocess.Popen(
                    command.args,
                    cwd=command.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            )

        for label, process in zip(("backend", "frontend"), processes, strict=True):
            threading.Thread(target=_stream_output, args=(label, process), daemon=True).start()

        while True:
            for label, process in zip(("backend", "frontend"), processes, strict=True):
                returncode = process.poll()
                if returncode is not None:
                    print(f"[{label}] exited unexpectedly with status {returncode}")
                    return 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("[shutdown] stopping development servers")
        return 0
    except OSError as exc:
        print(f"[error] unable to start development server: {exc}", file=sys.stderr)
        return 1
    finally:
        _stop_processes(processes)


def main() -> int:
    root = project_root()
    errors = preflight_errors(root)
    if errors:
        for error in errors:
            print(f"[error] {error}", file=sys.stderr)
        return 1

    try:
        run_setup(root)
    except CommandFailed as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return exc.returncode or 1
    return run_development(root)


if __name__ == "__main__":
    raise SystemExit(main())
