"""Tests for data_tools (convert, json-diff, flatten)."""

import json
from pathlib import Path

from scriptbox.cli import main


def test_convert_json_to_csv(tmp_path):
    """Test converting JSON list of objects to CSV."""
    json_file = tmp_path / "data.json"
    json_file.write_text(
        json.dumps([{"id": 1, "name": "Arvin", "role": "Developer"}, {"id": 2, "name": "Maria", "role": "Designer"}]),
        encoding="utf-8",
    )
    csv_file = tmp_path / "data.csv"

    code = main(["convert", str(json_file), "--to", "csv", "-o", str(csv_file)])
    assert code == 0
    assert csv_file.exists()
    content = csv_file.read_text(encoding="utf-8")
    assert "id,name,role" in content
    assert "1,Arvin,Developer" in content
    assert "2,Maria,Designer" in content


def test_json_diff_detection(tmp_path, capsys):
    """Test detecting added, removed, and modified keys in JSON diff."""
    file_a = tmp_path / "a.json"
    file_b = tmp_path / "b.json"

    file_a.write_text(json.dumps({"name": "ScriptBox", "version": "0.1.0", "deprecated": True}), encoding="utf-8")
    file_b.write_text(json.dumps({"name": "ScriptBox", "version": "0.2.0", "new_feature": "Diff"}), encoding="utf-8")

    code = main(["json-diff", str(file_a), str(file_b), "--json"])
    assert code == 1  # differences found
    captured = capsys.readouterr()
    diffs = json.loads(captured.out)

    paths = {d["path"]: d["type"] for d in diffs}
    assert paths.get("version") == "modified"
    assert paths.get("deprecated") == "removed"
    assert paths.get("new_feature") == "added"


def test_json_diff_identical(tmp_path, capsys):
    """Test diffing identical files returns 0."""
    file_a = tmp_path / "a.json"
    file_b = tmp_path / "b.json"

    file_a.write_text(json.dumps({"status": "ok", "code": 200}), encoding="utf-8")
    file_b.write_text(json.dumps({"status": "ok", "code": 200}), encoding="utf-8")

    code = main(["json-diff", str(file_a), str(file_b)])
    assert code == 0
    captured = capsys.readouterr()
    assert "semantically identical" in captured.out


def test_flatten_nested_json(tmp_path, capsys):
    """Test flattening nested JSON dictionary."""
    nested_file = tmp_path / "nested.json"
    nested_file.write_text(
        json.dumps({"user": {"profile": {"name": "Arvin", "location": "Bulacan"}}}),
        encoding="utf-8",
    )

    code = main(["flatten", str(nested_file)])
    assert code == 0
    captured = capsys.readouterr()
    flat = json.loads(captured.out)
    assert flat["user.profile.name"] == "Arvin"
    assert flat["user.profile.location"] == "Bulacan"
