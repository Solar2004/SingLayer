from singlayer.diagnostics import log_path, record


def test_diagnostic_records_only_supplied_categories(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    record("pronunciation_http", "response", status=403)
    record("pronunciation", "TimeoutError")
    text = log_path().read_text()
    assert "status=403" in text
    assert "TimeoutError" in text
    assert len(text) < 300


def test_unwritable_log_does_not_break_app(tmp_path, monkeypatch):
    invalid = tmp_path / "file"
    invalid.write_text("fixture")
    monkeypatch.setenv("XDG_STATE_HOME", str(invalid))
    record("test", "failure")
