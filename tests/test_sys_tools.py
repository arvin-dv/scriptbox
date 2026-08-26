"""Tests for sys_tools (disk-usage, port-info, purge-cache)."""

import json
from pathlib import Path

from scriptbox.cli import main


def test_disk_usage_json(tmp_path, capsys):
    """Test disk-usage analysis in JSON format."""
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "large.bin").write_bytes(b"A" * 1024)
    (tmp_path / "small.txt").write_text("hello", encoding="utf-8")

    code = main(["disk-usage", str(tmp_path), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) >= 1
    assert any(item["size_bytes"] >= 1024 for item in data)


def test_purge_cache_cleanup(tmp_path, capsys):
    """Test purge-cache cleans __pycache__ and .tmp files."""
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "module.cpython-312.pyc").write_bytes(b"\x00" * 100)
    (tmp_path / "temp.tmp").write_bytes(b"temp data")
    (tmp_path / "keep_me.py").write_text("print('keep me')", encoding="utf-8")

    # Dry run first
    code_dry = main(["purge-cache", str(tmp_path), "--dry-run"])
    assert code_dry == 0
    assert pycache.exists()
    assert (tmp_path / "temp.tmp").exists()

    # Actual purge
    code_actual = main(["purge-cache", str(tmp_path)])
    assert code_actual == 0
    assert not pycache.exists()
    assert not (tmp_path / "temp.tmp").exists()
    assert (tmp_path / "keep_me.py").exists()


def test_port_info_smoke():
    """Smoke test for port-info command execution."""
    code = main(["port-info", "65530", "--json"])
    assert code == 0
