"""Tests for media_tools (exif, img-info)."""

import json
import struct
from pathlib import Path

from scriptbox.cli import main


def create_sample_png(path: Path, width: int = 100, height: int = 80) -> None:
    """Create a minimal valid PNG binary header."""
    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">LLBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_len = struct.pack(">L", len(ihdr_data))
    ihdr_chunk = ihdr_len + b"IHDR" + ihdr_data + b"\x00\x00\x00\x00"
    path.write_bytes(header + ihdr_chunk)


def create_sample_bmp(path: Path, width: int = 50, height: int = 40) -> None:
    """Create a minimal valid BMP binary header."""
    bmp_header = b"BM" + (b"\x00" * 12)  # file header
    dib_header = struct.pack("<LllHH", 40, width, height, 1, 24) + (b"\x00" * 24)
    path.write_bytes(bmp_header + dib_header)


def test_img_info_png(tmp_path, capsys):
    """Test inspecting PNG dimensions."""
    png = tmp_path / "test.png"
    create_sample_png(png, width=320, height=240)

    code = main(["img-info", str(png), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["format"] == "PNG"
    assert data[0]["width"] == 320
    assert data[0]["height"] == 240


def test_img_info_bmp(tmp_path, capsys):
    """Test inspecting BMP dimensions."""
    bmp = tmp_path / "test.bmp"
    create_sample_bmp(bmp, width=64, height=64)

    code = main(["img-info", str(bmp), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["format"] == "BMP"
    assert data[0]["width"] == 64
    assert data[0]["height"] == 64


def test_exif_metadata_inspection(tmp_path, capsys):
    """Test exif inspection on a test file."""
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")

    code = main(["exif", str(img)])
    assert code == 0
    captured = capsys.readouterr()
    assert "photo.jpg" in captured.out
