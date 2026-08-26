"""Data serialization, format conversion, and diff utilities: convert, json-diff, flatten."""

import argparse
import csv
import io
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scriptbox.utils.console import (
    Colors,
    colorize,
    output_json_or_text,
    print_error,
    print_header,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from scriptbox.utils.files import read_text_safely, write_text_safely


def load_data(file_path: Optional[Path], raw_text: Optional[str] = None, format_hint: Optional[str] = None) -> Any:
    """Load and parse structured data from a file or string."""
    if file_path:
        text, _ = read_text_safely(file_path)
        ext = file_path.suffix.lower().lstrip(".")
        fmt = format_hint or ext
    else:
        text = raw_text or ""
        fmt = format_hint or "json"

    fmt = fmt.lower()

    if fmt == "json":
        return json.loads(text)

    if fmt in ("yaml", "yml"):
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            # Fallback simple json-compatible parser
            try:
                return json.loads(text)
            except Exception:
                raise ValueError("PyYAML is required for YAML parsing. Install with: pip install pyyaml")

    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)

    if fmt == "tsv":
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        return list(reader)

    if fmt == "toml":
        try:
            import tomllib  # Python 3.11+
            return tomllib.loads(text)
        except ImportError:
            try:
                import tomli
                return tomli.loads(text)
            except ImportError:
                raise ValueError("Python 3.11+ or 'tomli' package is required for TOML parsing.")

    if fmt == "xml":
        root = ET.fromstring(text)
        return elem_to_dict(root)

    # Default to json
    return json.loads(text)


def elem_to_dict(elem: ET.Element) -> Dict[str, Any]:
    """Convert an XML ElementTree element to a dictionary."""
    d: Dict[str, Any] = {elem.tag: {} if elem.attrib else None}
    children = list(elem)
    if children:
        dd: Dict[str, Any] = {}
        for dc in map(elem_to_dict, children):
            for k, v in dc.items():
                if k in dd:
                    if not isinstance(dd[k], list):
                        dd[k] = [dd[k]]
                    dd[k].append(v)
                else:
                    dd[k] = v
        d = {elem.tag: dd}
    if elem.attrib:
        d[elem.tag].update((f"@{k}", v) for k, v in elem.attrib.items())
    if elem.text:
        text = elem.text.strip()
        if children or elem.attrib:
            if text:
                d[elem.tag]["#text"] = text
        else:
            d[elem.tag] = text
    return d


def dump_data(data: Any, target_fmt: str, indent: int = 2) -> str:
    """Serialize Python data object to target format string."""
    target_fmt = target_fmt.lower()

    if target_fmt == "json":
        return json.dumps(data, indent=indent, default=str)

    if target_fmt in ("yaml", "yml"):
        try:
            import yaml
            return yaml.dump(data, sort_keys=False, default_flow_style=False)
        except ImportError:
            # Fallback JSON
            return json.dumps(data, indent=indent, default=str)

    if target_fmt in ("csv", "tsv"):
        delimiter = "\t" if target_fmt == "tsv" else ","
        if not isinstance(data, list):
            data = [data] if isinstance(data, dict) else [{"value": data}]

        # Flatten rows if nested
        flat_rows = [flatten_dict(item) if isinstance(item, dict) else {"value": item} for item in data]
        all_keys = []
        for r in flat_rows:
            for k in r.keys():
                if k not in all_keys:
                    all_keys.append(k)

        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=all_keys, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(flat_rows)
        return out.getvalue()

    if target_fmt == "toml":
        try:
            import tomli_w
            return tomli_w.dumps(data)
        except ImportError:
            # Simple fallback serializer for flat/simple dicts
            lines = []
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, (str, int, float, bool)):
                        lines.append(f"{k} = {json.dumps(v)}")
                    elif isinstance(v, dict):
                        lines.append(f"\n[{k}]")
                        for sub_k, sub_v in v.items():
                            lines.append(f"{sub_k} = {json.dumps(sub_v)}")
                return "\n".join(lines)
            raise ValueError("tomli-w required for complex TOML serialization. Install with: pip install tomli-w")

    raise ValueError(f"Unsupported target format: {target_fmt}")


def flatten_dict(d: Any, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Recursively flatten nested dictionary or list."""
    items: List[Tuple[str, Any]] = []
    if isinstance(d, dict):
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            if isinstance(v, (dict, list)):
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            new_key = f"{parent_key}[{i}]"
            if isinstance(v, (dict, list)):
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
    else:
        return {parent_key: d}
    return dict(items)


def diff_data(a: Any, b: Any, path: str = "") -> List[Dict[str, Any]]:
    """Semantically diff two data structures."""
    diffs: List[Dict[str, Any]] = []

    if type(a) != type(b):
        diffs.append({
            "type": "type_mismatch",
            "path": path or "/",
            "old": a,
            "new": b,
        })
        return diffs

    if isinstance(a, dict):
        all_keys = set(a.keys()) | set(b.keys())
        for k in sorted(all_keys):
            sub_path = f"{path}.{k}" if path else str(k)
            if k not in a:
                diffs.append({"type": "added", "path": sub_path, "value": b[k]})
            elif k not in b:
                diffs.append({"type": "removed", "path": sub_path, "value": a[k]})
            else:
                diffs.extend(diff_data(a[k], b[k], sub_path))

    elif isinstance(a, list):
        max_len = max(len(a), len(b))
        for i in range(max_len):
            sub_path = f"{path}[{i}]"
            if i >= len(a):
                diffs.append({"type": "added", "path": sub_path, "value": b[i]})
            elif i >= len(b):
                diffs.append({"type": "removed", "path": sub_path, "value": a[i]})
            else:
                diffs.extend(diff_data(a[i], b[i], sub_path))
    else:
        if a != b:
            diffs.append({"type": "modified", "path": path or "/", "old": a, "new": b})

    return diffs


def register_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register data manipulation subcommands."""

    # 1. convert
    p_conv = subparsers.add_parser(
        "convert",
        help="Convert structured data files between JSON, CSV, TSV, YAML, TOML, and XML.",
        description="Transform files or standard input into different structured data formats.",
    )
    p_conv.add_argument("input_file", nargs="?", help="Input file path (reads from stdin if omitted).")
    p_conv.add_argument("-t", "--to", required=True, choices=["json", "csv", "tsv", "yaml", "toml"], help="Target format.")
    p_conv.add_argument("-f", "--from", dest="from_format", choices=["json", "csv", "tsv", "yaml", "toml", "xml"], help="Source format hint.")
    p_conv.add_argument("-o", "--output", help="Write output to specified file path instead of stdout.")
    p_conv.add_argument("--indent", type=int, default=2, help="Indentation spaces for JSON (default: 2).")
    p_conv.set_defaults(func=cmd_convert)

    # 2. json-diff
    p_diff = subparsers.add_parser(
        "json-diff",
        help="Semantically compare two JSON / YAML / TOML data structures.",
        description="Compute structural differences between two data files, highlighting added, removed, and changed keys.",
    )
    p_diff.add_argument("file_a", help="First data file (original).")
    p_diff.add_argument("file_b", help="Second data file (modified).")
    p_diff.add_argument("--json", action="store_true", help="Output differences as JSON.")
    p_diff.set_defaults(func=cmd_json_diff)

    # 3. flatten
    p_flat = subparsers.add_parser(
        "flatten",
        help="Flatten nested JSON/dictionary structures into flat dot-notation keys.",
        description="Recursively flatten hierarchical objects or export nested structures as tabular CSV.",
    )
    p_flat.add_argument("file", nargs="?", help="Input JSON file path (reads from stdin if omitted).")
    p_flat.add_argument("-o", "--output", help="Output file path.")
    p_flat.add_argument("--csv", action="store_true", help="Output flattened structure as CSV.")
    p_flat.set_defaults(func=cmd_flatten)


def cmd_convert(args: argparse.Namespace) -> int:
    """Execute data format conversion."""
    try:
        if args.input_file:
            data = load_data(Path(args.input_file), format_hint=args.from_format)
        else:
            raw = sys.stdin.read()
            data = load_data(None, raw_text=raw, format_hint=args.from_format or "json")

        result = dump_data(data, args.to, indent=args.indent)
        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
            print_success(f"Converted data to {args.to.upper()} -> {args.output}")
        else:
            print(result)
        return 0
    except Exception as e:
        print_error(f"Conversion failed: {e}")
        return 1


def cmd_json_diff(args: argparse.Namespace) -> int:
    """Execute semantic data diff."""
    try:
        data_a = load_data(Path(args.file_a))
        data_b = load_data(Path(args.file_b))
        diffs = diff_data(data_a, data_b)

        if args.json:
            output_json_or_text(diffs, as_json=True)
            return 0 if not diffs else 1

        if not diffs:
            print_success("Files are semantically identical.")
            return 0

        print_header(f"Data Diff: {args.file_a} <-> {args.file_b} ({len(diffs)} differences)")
        for d in diffs:
            dtype = d["type"]
            path = d["path"]
            if dtype == "added":
                print(colorize(f"+ [ADDED]    {path} = {json.dumps(d['value'])}", Colors.GREEN))
            elif dtype == "removed":
                print(colorize(f"- [REMOVED]  {path} = {json.dumps(d['value'])}", Colors.RED))
            elif dtype == "modified":
                print(colorize(f"~ [MODIFIED] {path}: {json.dumps(d['old'])} -> {json.dumps(d['new'])}", Colors.YELLOW))
            elif dtype == "type_mismatch":
                print(colorize(f"! [MISMATCH] {path}: {type(d['old']).__name__} -> {type(d['new']).__name__}", Colors.MAGENTA))

        return 1
    except Exception as e:
        print_error(f"Diff failed: {e}")
        return 1


def cmd_flatten(args: argparse.Namespace) -> int:
    """Execute dictionary flattening."""
    try:
        if args.file:
            data = load_data(Path(args.file))
        else:
            raw = sys.stdin.read()
            data = load_data(None, raw_text=raw)

        if isinstance(data, list):
            flat = [flatten_dict(item) for item in data]
        else:
            flat = flatten_dict(data)

        if args.csv:
            result = dump_data(flat, "csv")
        else:
            result = json.dumps(flat, indent=2, default=str)

        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
            print_success(f"Flattened data saved to {args.output}")
        else:
            print(result)
        return 0
    except Exception as e:
        print_error(f"Flattening failed: {e}")
        return 1
