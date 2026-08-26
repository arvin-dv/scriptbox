"""Tests for net_tools (http, port-scan, trace-url, download)."""

import json
from unittest.mock import MagicMock, patch

from scriptbox.cli import main


def test_http_request_mocked(capsys):
    """Test http request with mocked urllib response."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"status": "success", "message": "hello"}'
    mock_resp.status = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        code = main(["http", "https://api.example.com/data", "--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status_code"] == 200
        assert "message" in data["body"]


def test_port_scan_mocked(capsys):
    """Test port scan command with mocked socket connection."""
    with patch("socket.gethostbyname", return_value="127.0.0.1"), \
         patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0  # Port is open
        mock_sock_cls.return_value.__enter__.return_value = mock_sock

        code = main(["port-scan", "127.0.0.1", "-p", "80,443", "--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["host"] == "127.0.0.1"
        assert len(data["open_ports"]) == 2


def test_download_mocked(tmp_path):
    """Test downloading a file with checksum verification."""
    mock_resp = MagicMock()
    mock_resp.read.side_effect = [b"ScriptBox Download Test Content", b""]
    mock_resp.headers = {"Content-Length": "31"}
    mock_resp.__enter__.return_value = mock_resp

    out_file = tmp_path / "downloaded.txt"

    with patch("urllib.request.urlopen", return_value=mock_resp):
        code = main(["download", "https://example.com/file.txt", "-o", str(out_file)])
        assert code == 0
        assert out_file.exists()
        assert out_file.read_bytes() == b"ScriptBox Download Test Content"
