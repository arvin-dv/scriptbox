"""Tests for ScriptBox main CLI entry point."""

import sys
from io import StringIO
from unittest.mock import patch

import pytest
from scriptbox import __version__
from scriptbox.cli import build_parser, main


def test_cli_version(capsys):
    """Test --version flag outputs version."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_help(capsys):
    """Test --help outputs all tool suites."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Available ScriptBox Tool Suites:" in captured.out
    assert "Text & Files:" in captured.out
    assert "Developer & Code:" in captured.out
    assert "System & Diagnostics:" in captured.out
    assert "Data & Formats:" in captured.out
    assert "Network & Web:" in captured.out
    assert "Security & Crypto:" in captured.out
    assert "Media & Privacy:" in captured.out


def test_cli_no_args_shows_help(capsys):
    """Test running CLI with no args shows help."""
    code = main([])
    assert code == 0
    captured = capsys.readouterr()
    assert "usage: scriptbox" in captured.out


def test_cli_unknown_command(capsys):
    """Test unknown command exits with error."""
    with pytest.raises(SystemExit) as exc:
        main(["nonexistent-command"])
    assert exc.value.code != 0
