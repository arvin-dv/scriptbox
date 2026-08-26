"""Tests for text_tools (replace, dedup, charset, crlf)."""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scriptbox.cli import main


def test_replace_dry_run(tmp_path, capsys):
    """Test replace command with --dry-run does not modify file."""
    f = tmp_path / "hello.txt"
    f.write_text("Hello World! Hello Universe!", encoding="utf-8")

    code = main(["replace", "World", "Earth", str(f), "--dry-run"])
    assert code == 0
    assert f.read_text(encoding="utf-8") == "Hello World! Hello Universe!"
    captured = capsys.readouterr()
    assert "-Hello World!" in captured.out or "World" in captured.out
    assert "+Hello Earth!" in captured.out or "Earth" in captured.out


def test_replace_actual_and_backup(tmp_path):
    """Test replace with actual modification and .bak backup."""
    f = tmp_path / "sample.py"
    f.write_text("foo = 1\nbar = foo + 1\n", encoding="utf-8")

    code = main(["replace", "foo", "qux", str(f), "--backup"])
    assert code == 0
    assert f.read_text(encoding="utf-8") == "qux = 1\nbar = qux + 1\n"
    bak = tmp_path / "sample.py.bak"
    assert bak.exists()
    assert bak.read_text(encoding="utf-8") == "foo = 1\nbar = foo + 1\n"


def test_dedup_file(tmp_path, capsys):
    """Test deduping lines from a file."""
    f = tmp_path / "list.txt"
    f.write_text("apple\nbanana\napple\norange\nbanana\n", encoding="utf-8")

    code = main(["dedup", str(f)])
    assert code == 0
    captured = capsys.readouterr()
    lines = [line.strip() for line in captured.out.strip().splitlines()]
    assert lines == ["apple", "banana", "orange"]


def test_dedup_with_count_and_sort(tmp_path, capsys):
    """Test dedup with count and alphabetical sort."""
    f = tmp_path / "counts.txt"
    f.write_text("zebra\napple\nzebra\nbanana\n", encoding="utf-8")

    code = main(["dedup", str(f), "--count", "--sort"])
    assert code == 0
    captured = capsys.readouterr()
    assert "apple" in captured.out
    assert "zebra" in captured.out
    assert "2  zebra" in captured.out


def test_crlf_normalization(tmp_path):
    """Test converting CRLF to LF."""
    f = tmp_path / "crlf.txt"
    f.write_bytes(b"line1\r\nline2\r\nline3\r\n")

    code = main(["crlf", str(f), "--to", "lf"])
    assert code == 0
    assert f.read_bytes() == b"line1\nline2\nline3\n"

    # Convert back to crlf
    code2 = main(["crlf", str(f), "--to", "crlf"])
    assert code2 == 0
    assert f.read_bytes() == b"line1\r\nline2\r\nline3\r\n"


def test_charset_detection(tmp_path, capsys):
    """Test detecting utf-8 charset."""
    f = tmp_path / "utf8.txt"
    f.write_text("Mabuhay ang Pilipinas! 🇵🇭", encoding="utf-8")

    code = main(["charset", str(f)])
    assert code == 0
    captured = capsys.readouterr()
    assert "utf-8" in captured.out.lower()
