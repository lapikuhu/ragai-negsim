import logging

from app.core.logging import SafeRotatingFileHandler, configure_logging


def test_safe_rotating_file_handler_ignores_locked_windows_rollover(tmp_path, monkeypatch):
    log_path = tmp_path / "app.log"
    log_path.write_text("existing log line\n", encoding="utf-8")
    handler = SafeRotatingFileHandler(
        filename=log_path,
        maxBytes=1,
        backupCount=1,
        encoding="utf-8",
    )

    def locked_rotate(source, dest):
        raise PermissionError(32, "file is locked", source)

    monkeypatch.setattr(handler, "rotate", locked_rotate)

    handler.doRollover()
    handler.emit(logging.makeLogRecord({"msg": "still logging", "levelno": logging.INFO}))
    handler.close()

    assert "still logging" in log_path.read_text(encoding="utf-8")


def test_configure_logging_quiets_dependency_http_request_logs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    configure_logging()

    assert logging.getLogger("app").getEffectiveLevel() == logging.INFO
    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING
