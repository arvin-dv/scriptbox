"""Tests for crypto_tools (hash, passgen, jwt-decode, b64)."""

import base64
import datetime
import hashlib
import json
from pathlib import Path

from scriptbox.cli import main


def test_hash_string(capsys):
    """Test hashing a literal string with SHA256."""
    text = "Hello ScriptBox!"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()

    code = main(["hash", "-s", text, "-a", "sha256"])
    assert code == 0
    captured = capsys.readouterr()
    assert expected in captured.out


def test_hash_manifest_check(tmp_path, capsys):
    """Test generating and checking a checksums manifest file."""
    f1 = tmp_path / "file1.txt"
    f2 = tmp_path / "file2.txt"
    f1.write_text("file 1 content", encoding="utf-8")
    f2.write_text("file 2 content", encoding="utf-8")

    h1 = hashlib.sha256(f1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(f2.read_bytes()).hexdigest()

    manifest = tmp_path / "checksums.sha256"
    manifest.write_text(f"{h1}  file1.txt\n{h2}  file2.txt\n", encoding="utf-8")

    code = main(["hash", "--check", str(manifest)])
    assert code == 0
    captured = capsys.readouterr()
    assert "file1.txt: OK" in captured.out
    assert "file2.txt: OK" in captured.out
    assert "All 2 files verified successfully" in captured.out


def test_passgen_length(capsys):
    """Test password generation produces exact requested length."""
    code = main(["passgen", "-l", "24", "-n", "3", "--no-symbols"])
    assert code == 0
    captured = capsys.readouterr()
    lines = [line.split()[0] for line in captured.out.strip().splitlines() if line]
    assert len(lines) == 3
    for pwd in lines:
        assert len(pwd) == 24
        assert pwd.isalnum()


def test_passgen_diceware(capsys):
    """Test Diceware passphrase generation."""
    code = main(["passgen", "-w", "4", "-s", "_"])
    assert code == 0
    captured = capsys.readouterr()
    pwd = captured.out.split()[0]
    words = pwd.split("_")
    assert len(words) == 4


def test_jwt_decode(capsys):
    """Test decoding and expiration check for JWT."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode("utf-8").rstrip("=")
    future_exp = int(datetime.datetime.now().timestamp()) + 3600
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "arvin123", "role": "admin", "exp": future_exp}).encode("utf-8")).decode("utf-8").rstrip("=")
    signature = "dummy_signature"

    jwt_token = f"{header}.{payload}.{signature}"

    code = main(["jwt-decode", jwt_token])
    assert code == 0
    captured = capsys.readouterr()
    assert "arvin123" in captured.out
    assert "admin" in captured.out
    assert "TOKEN IS VALID" in captured.out


def test_b64_encode_and_decode(capsys):
    """Test base64 encoding and decoding roundtrip."""
    text = "Bulacan State University"

    # Encode
    code_enc = main(["b64", text])
    assert code_enc == 0
    captured_enc = capsys.readouterr()
    encoded = captured_enc.out.strip()

    # Decode
    code_dec = main(["b64", encoded, "-d"])
    assert code_dec == 0
    captured_dec = capsys.readouterr()
    assert captured_dec.out.strip() == text
