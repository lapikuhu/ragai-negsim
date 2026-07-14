from pathlib import Path

import pytest

from scripts import dev


def test_setup_commands_use_locked_dependencies_and_existing_migrations(tmp_path):
    commands = dev.setup_commands(tmp_path)

    assert [(command.args, command.cwd) for command in commands] == [
        (("uv", "sync", "--frozen"), tmp_path),
        (("npm", "ci"), tmp_path / "frontend"),
        (("uv", "run", "alembic", "upgrade", "head"), tmp_path),
        (("uv", "run", "python", "scripts/seeder.py"), tmp_path),
    ]


def test_run_setup_stops_after_the_first_failed_command(tmp_path):
    executed = []

    def runner(command):
        executed.append(command)
        if command.args == ("npm", "ci"):
            raise dev.CommandFailed(command, 1)

    with pytest.raises(dev.CommandFailed):
        dev.run_setup(tmp_path, runner)

    assert [command.args for command in executed] == [
        ("uv", "sync", "--frozen"),
        ("npm", "ci"),
    ]


def test_preflight_reports_missing_env_file_and_executables(tmp_path):
    errors = dev.preflight_errors(
        tmp_path,
        python_version=(3, 12),
        which=lambda executable: None,
    )

    assert errors == [
        f"Missing environment file: {tmp_path / '.env'}",
        "Required executable not found on PATH: uv",
        "Required executable not found on PATH: npm",
    ]


def test_development_commands_match_the_existing_local_servers(tmp_path):
    backend, frontend = dev.development_commands(tmp_path)

    assert backend.args == ("uv", "run", "uvicorn", "app.main:app", "--reload")
    assert backend.cwd == tmp_path
    assert frontend.args == ("npm", "run", "dev")
    assert frontend.cwd == tmp_path / "frontend"


def test_unexpected_server_exit_stops_the_sibling(monkeypatch, tmp_path):
    class FakeProcess:
        def __init__(self, returncode):
            self.returncode = returncode
            self.stdout = []
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.returncode = 1

    backend = FakeProcess(returncode=1)
    frontend = FakeProcess(returncode=None)
    processes = iter((backend, frontend))

    monkeypatch.setattr(dev.subprocess, "Popen", lambda *args, **kwargs: next(processes))

    assert dev.run_development(tmp_path) == 1
    assert frontend.terminated is True
