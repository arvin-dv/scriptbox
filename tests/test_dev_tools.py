"""Tests for dev_tools (scan-secrets, todos, license-check)."""

import json
from pathlib import Path

from scriptbox.cli import main


def test_scan_secrets_detection(tmp_path, capsys):
    """Test detecting AWS and OpenAI secrets with masking."""
    f = tmp_path / "config.py"
    f.write_text(
        'AWS_KEY = "AKIA1234567890ABCDEF"\n'
        'OPENAI_KEY = "sk-1234567890abcdef1234567890abcdef"\n',
        encoding="utf-8",
    )

    code = main(["scan-secrets", str(tmp_path), "--fail-on-found"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Found 2 Potential Secret" in captured.out
    assert "AWS Access Key ID" in captured.out
    assert "OpenAI API Key" in captured.out
    # Ensure masked
    assert "AKI" in captured.out
    assert "sk-" in captured.out
    assert "1234567890" not in captured.out


def test_scan_secrets_clean_directory(tmp_path, capsys):
    """Test scanning a clean directory exits with 0."""
    f = tmp_path / "clean.py"
    f.write_text('def hello():\n    return "world"\n', encoding="utf-8")

    code = main(["scan-secrets", str(tmp_path), "--fail-on-found"])
    assert code == 0
    captured = capsys.readouterr()
    assert "No secrets or exposed credentials detected" in captured.out


def test_todos_extractor(tmp_path, capsys):
    """Test extracting TODO and FIXME comments."""
    f = tmp_path / "app.py"
    f.write_text(
        "# TODO(arvin): add database migration\n"
        "def query():\n"
        "    # FIXME: handle connection timeout\n"
        "    pass\n",
        encoding="utf-8",
    )

    code = main(["todos", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "TODO" in captured.out
    assert "FIXME" in captured.out
    assert "add database migration" in captured.out
    assert "handle connection timeout" in captured.out


def test_todos_json_format(tmp_path, capsys):
    """Test exporting TODOs to JSON."""
    f = tmp_path / "todo.js"
    f.write_text("// NOTE: review this algorithm\n", encoding="utf-8")

    code = main(["todos", str(tmp_path), "--format", "json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["tag"] == "NOTE"
    assert "review this algorithm" in data[0]["message"]


def test_license_check_and_inject(tmp_path):
    """Test license header injection."""
    f = tmp_path / "script.py"
    f.write_text('print("hello")\n', encoding="utf-8")

    # Check without injection should warn
    code = main(["license-check", str(tmp_path), "--holder", "BulSU Team"])
    assert code == 0
    assert "BulSU Team" not in f.read_text(encoding="utf-8")

    # Inject
    code_inject = main(["license-check", str(tmp_path), "--holder", "BulSU Team", "--inject"])
    assert code_inject == 0
    content = f.read_text(encoding="utf-8")
    assert "Copyright (c) 2026 BulSU Team" in content
    assert 'print("hello")' in content
