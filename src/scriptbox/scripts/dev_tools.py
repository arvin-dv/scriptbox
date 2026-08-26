"""Developer productivity & code hygiene tools: scan-secrets, todos, license-check."""

import argparse
import math
import re
import sys
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
from scriptbox.utils.files import find_files, read_text_safely, write_text_safely


SECRET_PATTERNS = [
    ("AWS Access Key ID", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
    ("AWS Secret Key", re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?")),
    ("GitHub Personal Access Token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,255})\b")),
    ("GitHub Fine-Grained Token", re.compile(r"\b(github_pat_[A-Za-z0-9_]{82})\b")),
    ("OpenAI API Key", re.compile(r"\b(sk-[A-Za-z0-9]{20,64})\b")),
    ("Google API Key / Gemini", re.compile(r"\b(AIza[0-9A-Za-z-_]{35})\b")),
    ("Slack Token", re.compile(r"\b(xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*)\b")),
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("Database URI with Password", re.compile(r"[a-zA-Z0-9_+]+:\/\/[a-zA-Z0-9_.-]+:([^@\s]{3,})@[a-zA-Z0-9_.-]+")),
    ("Generic Bearer / API Secret", re.compile(r"(?i)(?:api_key|apikey|secret_token|auth_token)\s*[:=]\s*['\"]([A-Za-z0-9_\-]{20,})['\"]")),
]

TODO_REGEX = re.compile(
    r"(?i)\b(TODO|FIXME|BUG|HACK|XXX|NOTE|OPTIMIZE)\b(?:\(([^)]+)\))?[:\s]*(.*)",
)


def calc_shannon_entropy(data: str) -> float:
    """Calculate the Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    for x in set(data):
        p_x = float(data.count(x)) / len(data)
        if p_x > 0:
            entropy += - p_x * math.log2(p_x)
    return entropy


def mask_secret(secret: str) -> str:
    """Mask sensitive string, revealing only first and last 2 characters."""
    if len(secret) <= 6:
        return "*" * len(secret)
    return secret[:3] + "*" * (len(secret) - 6) + secret[-3:]


def register_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register developer tool subcommands."""

    # 1. scan-secrets
    p_secrets = subparsers.add_parser(
        "scan-secrets",
        help="Scan code and text files for accidental API keys, tokens, and credentials.",
        description="Search directory trees for secrets, private keys, and high-entropy tokens.",
    )
    p_secrets.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Directories or files to scan (default: current directory).",
    )
    p_secrets.add_argument(
        "--entropy",
        action="store_true",
        help="Also flag high-entropy hex/base64 strings (> 4.5 Shannon entropy).",
    )
    p_secrets.add_argument(
        "--unmask",
        action="store_true",
        help="Show full raw secrets instead of masked strings (Warning: reveals secrets).",
    )
    p_secrets.add_argument(
        "--json",
        action="store_true",
        help="Output findings formatted as JSON.",
    )
    p_secrets.add_argument(
        "--fail-on-found",
        action="store_true",
        help="Exit with non-zero status code if any secret is discovered (useful for CI).",
    )
    p_secrets.set_defaults(func=cmd_scan_secrets)

    # 2. todos
    p_todos = subparsers.add_parser(
        "todos",
        help="Extract TODO, FIXME, BUG, HACK, and NOTE comments across codebase.",
        description="Aggregate code annotations with line numbers, tags, and optional markdown export.",
    )
    p_todos.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Directories or files to inspect (default: current directory).",
    )
    p_todos.add_argument(
        "--tag",
        action="append",
        help="Filter specific tag (e.g. --tag FIXME --tag BUG).",
    )
    p_todos.add_argument(
        "--format",
        choices=["table", "markdown", "json"],
        default="table",
        help="Output format: table (default), markdown checklist, or json.",
    )
    p_todos.set_defaults(func=cmd_todos)

    # 3. license-check
    p_license = subparsers.add_parser(
        "license-check",
        help="Validate and inject license headers into source files.",
        description="Ensure all source files contain the required license or copyright notice.",
    )
    p_license.add_argument(
        "paths",
        nargs="+",
        help="Directories or files to check.",
    )
    p_license.add_argument(
        "--holder",
        required=True,
        help="Copyright holder name to look for or inject.",
    )
    p_license.add_argument(
        "--year",
        default="2026",
        help="Copyright year (default: 2026).",
    )
    p_license.add_argument(
        "--inject",
        action="store_true",
        help="Automatically inject missing header into source files.",
    )
    p_license.add_argument(
        "--glob",
        dest="glob_patterns",
        action="append",
        help="Filter glob patterns (e.g. '*.py', '*.js').",
    )
    p_license.set_defaults(func=cmd_license_check)


def cmd_scan_secrets(args: argparse.Namespace) -> int:
    """Execute secret scanner."""
    findings: List[Dict[str, Any]] = []

    for path_arg in args.paths:
        p = Path(path_arg)
        files = find_files(p) if p.is_dir() else [p]

        for file_path in files:
            if not file_path.is_file():
                continue

            try:
                content, _ = read_text_safely(file_path)
            except Exception:
                continue

            lines = content.splitlines()
            for line_idx, line in enumerate(lines, start=1):
                # Pattern scanning
                for label, regex in SECRET_PATTERNS:
                    match = regex.search(line)
                    if match:
                        raw_val = match.group(1) if match.groups() else match.group(0)
                        val_display = raw_val if args.unmask else mask_secret(raw_val)
                        findings.append({
                            "file": str(file_path),
                            "line": line_idx,
                            "type": label,
                            "match": val_display,
                        })

                # Entropy scanning
                if args.entropy:
                    tokens = re.findall(r"\b[A-Za-z0-9+/=_-]{24,}\b", line)
                    for token in tokens:
                        ent = calc_shannon_entropy(token)
                        if ent >= 4.5:
                            findings.append({
                                "file": str(file_path),
                                "line": line_idx,
                                "type": f"High Entropy ({ent:.2f})",
                                "match": token if args.unmask else mask_secret(token),
                            })

    if args.json:
        output_json_or_text(findings, as_json=True)
    else:
        if findings:
            print_header(f"Found {len(findings)} Potential Secret(s)")
            table_rows = [
                [f["file"], str(f["line"]), f["type"], f["match"]]
                for f in findings
            ]
            print_table(["File", "Line", "Secret Type", "Snippet / Token"], table_rows)
            print_warning("Review flagged items immediately. Rotate any genuine leaked credentials.")
        else:
            print_success("No secrets or exposed credentials detected.")

    if args.fail_on_found and findings:
        return 1
    return 0


def cmd_todos(args: argparse.Namespace) -> int:
    """Extract todos and code annotations."""
    todos: List[Dict[str, Any]] = []
    filter_tags = [t.upper() for t in args.tag] if args.tag else None

    for path_arg in args.paths:
        p = Path(path_arg)
        files = find_files(p) if p.is_dir() else [p]

        for file_path in files:
            if not file_path.is_file():
                continue

            try:
                content, _ = read_text_safely(file_path)
            except Exception:
                continue

            for line_idx, line in enumerate(content.splitlines(), start=1):
                match = TODO_REGEX.search(line)
                if match:
                    tag = match.group(1).upper()
                    assignee = match.group(2) or ""
                    message = match.group(3).strip()

                    if filter_tags and tag not in filter_tags:
                        continue

                    todos.append({
                        "file": str(file_path),
                        "line": line_idx,
                        "tag": tag,
                        "assignee": assignee,
                        "message": message,
                    })

    if args.format == "json":
        output_json_or_text(todos, as_json=True)
    elif args.format == "markdown":
        print("# Code Annotations & TODOs\n")
        current_file = None
        for t in todos:
            if t["file"] != current_file:
                current_file = t["file"]
                print(f"\n### `{current_file}`")
            assignee_str = f" (**@{t['assignee']}**)" if t["assignee"] else ""
            print(f"- [ ] **Line {t['line']}** `[{t['tag']}]`{assignee_str}: {t['message']}")
    else:
        if todos:
            print_header(f"Found {len(todos)} Code Annotation(s)")
            table_rows = [
                [t["file"], str(t["line"]), t["tag"], t["assignee"] or "-", t["message"][:60]]
                for t in todos
            ]
            print_table(["File", "Line", "Tag", "Assignee", "Comment"], table_rows)
        else:
            print_success("No TODO/FIXME annotations found.")

    return 0


def cmd_license_check(args: argparse.Namespace) -> int:
    """Validate and inject license headers."""
    expected_substring = args.holder.lower()
    missing: List[Path] = []
    checked_count = 0

    for path_arg in args.paths:
        p = Path(path_arg)
        files = find_files(p, include_patterns=args.glob_patterns) if p.is_dir() else [p]

        for file_path in files:
            if not file_path.is_file():
                continue

            checked_count += 1
            content, enc = read_text_safely(file_path)
            # Check first 20 lines
            header_snippet = "\n".join(content.splitlines()[:20]).lower()

            if expected_substring not in header_snippet:
                missing.append(file_path)
                if args.inject:
                    comment_prefix = "#" if file_path.suffix in [".py", ".sh", ".yaml", ".yml", ".toml"] else "//"
                    header = (
                        f"{comment_prefix} Copyright (c) {args.year} {args.holder}. All rights reserved.\n"
                        f"{comment_prefix} SPDX-License-Identifier: MIT\n\n"
                    )
                    write_text_safely(file_path, header + content, encoding=enc)
                    print_info(f"Injected header into {file_path}")

    if missing:
        if args.inject:
            print_success(f"Injected license header into {len(missing)} of {checked_count} file(s).")
        else:
            print_warning(f"{len(missing)} of {checked_count} file(s) are missing copyright notice for '{args.holder}':")
            for m in missing:
                print(f"  - {m}")
    else:
        print_success(f"All {checked_count} inspected files contain valid copyright headers.")

    return 0
