"""Text and file manipulation CLI utilities: replace, dedup, charset, crlf."""

import argparse
import difflib
import re
import sys
from pathlib import Path
from typing import List, Optional

from scriptbox.utils.console import (
    Colors,
    colorize,
    print_error,
    print_header,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from scriptbox.utils.files import (
    detect_encoding,
    find_files,
    read_text_safely,
    write_text_safely,
)


def register_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register text manipulation subcommands."""

    # 1. replace
    p_replace = subparsers.add_parser(
        "replace",
        help="Find and replace text or regex patterns across multiple files with diff preview.",
        description="Search and replace strings or regular expressions across files and directories.",
    )
    p_replace.add_argument("pattern", help="Regex or literal string pattern to search for.")
    p_replace.add_argument("replacement", help="Replacement text.")
    p_replace.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to process.",
    )
    p_replace.add_argument(
        "--glob",
        dest="glob_patterns",
        action="append",
        help="Include file glob patterns (e.g. '*.py', '*.md').",
    )
    p_replace.add_argument(
        "-i",
        "--ignore-case",
        action="store_true",
        help="Case-insensitive regex matching.",
    )
    p_replace.add_argument(
        "--literal",
        action="store_true",
        help="Treat pattern and replacement as literal strings rather than regex.",
    )
    p_replace.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Show unified diff preview without modifying files on disk.",
    )
    p_replace.add_argument(
        "-b",
        "--backup",
        action="store_true",
        help="Create a .bak backup before modifying any file.",
    )
    p_replace.set_defaults(func=cmd_replace)

    # 2. dedup
    p_dedup = subparsers.add_parser(
        "dedup",
        help="Deduplicate lines in files or stdin while preserving order.",
        description="Remove duplicate lines with options to count, trim whitespace, or sort.",
    )
    p_dedup.add_argument(
        "files",
        nargs="*",
        help="File paths to deduplicate (reads from stdin if omitted).",
    )
    p_dedup.add_argument(
        "-o",
        "--output",
        help="Write deduplicated output to specified file path instead of stdout.",
    )
    p_dedup.add_argument(
        "-i",
        "--ignore-case",
        action="store_true",
        help="Ignore line casing when checking for duplicates.",
    )
    p_dedup.add_argument(
        "-t",
        "--trim",
        action="store_true",
        help="Trim leading and trailing whitespace before comparison.",
    )
    p_dedup.add_argument(
        "-c",
        "--count",
        action="store_true",
        help="Prefix output lines with duplicate occurrence count.",
    )
    p_dedup.add_argument(
        "-s",
        "--sort",
        action="store_true",
        help="Sort unique output lines alphabetically.",
    )
    p_dedup.set_defaults(func=cmd_dedup)

    # 3. charset
    p_charset = subparsers.add_parser(
        "charset",
        help="Detect and convert text file character encodings.",
        description="Inspect or convert character encodings of files (e.g. Latin-1/CP1252 to UTF-8).",
    )
    p_charset.add_argument(
        "files",
        nargs="+",
        help="Files or directories to inspect/convert.",
    )
    p_charset.add_argument(
        "--to",
        dest="target_encoding",
        default="utf-8",
        help="Target encoding to convert files to (default: utf-8).",
    )
    p_charset.add_argument(
        "-c",
        "--convert",
        action="store_true",
        help="Convert files to the target encoding (defaults to inspection only).",
    )
    p_charset.add_argument(
        "-b",
        "--backup",
        action="store_true",
        help="Create a .bak backup before converting.",
    )
    p_charset.set_defaults(func=cmd_charset)

    # 4. crlf
    p_crlf = subparsers.add_parser(
        "crlf",
        help="Normalize line endings across source files (LF <-> CRLF).",
        description="Convert newline formatting across files or directories.",
    )
    p_crlf.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to normalize.",
    )
    p_crlf.add_argument(
        "--to",
        choices=["lf", "crlf"],
        default="lf",
        help="Target newline format: 'lf' (Unix) or 'crlf' (Windows). Default: lf.",
    )
    p_crlf.add_argument(
        "--glob",
        dest="glob_patterns",
        action="append",
        help="Filter file glob patterns (e.g. '*.py', '*.js').",
    )
    p_crlf.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files.",
    )
    p_crlf.set_defaults(func=cmd_crlf)


def cmd_replace(args: argparse.Namespace) -> int:
    """Execute find-and-replace command."""
    flags = re.IGNORECASE if args.ignore_case else 0
    pattern_str = re.escape(args.pattern) if args.literal else args.pattern

    try:
        regex = re.compile(pattern_str, flags)
    except re.error as e:
        print_error(f"Invalid regular expression pattern '{args.pattern}': {e}")
        return 1

    total_files_matched = 0
    total_replacements = 0

    for path_arg in args.paths:
        p = Path(path_arg)
        file_gen = find_files(p, include_patterns=args.glob_patterns) if p.is_dir() else [p]

        for file_path in file_gen:
            if not file_path.is_file():
                continue

            try:
                original_content, encoding = read_text_safely(file_path)
            except Exception as e:
                print_warning(f"Could not read {file_path}: {e}")
                continue

            if args.literal:
                if args.ignore_case:
                    new_content, count = regex.subn(args.replacement, original_content)
                else:
                    count = original_content.count(args.pattern)
                    new_content = original_content.replace(args.pattern, args.replacement)
            else:
                new_content, count = regex.subn(args.replacement, original_content)

            if count > 0:
                total_files_matched += 1
                total_replacements += count
                print_info(f"File {file_path} ({count} match{'es' if count > 1 else ''}):")

                # Show unified diff
                diff_lines = list(
                    difflib.unified_diff(
                        original_content.splitlines(keepends=True),
                        new_content.splitlines(keepends=True),
                        fromfile=f"a/{file_path.name}",
                        tofile=f"b/{file_path.name}",
                        n=2,
                    )
                )
                for line in diff_lines:
                    if line.startswith("+") and not line.startswith("+++"):
                        print(colorize(line.rstrip("\r\n"), Colors.GREEN))
                    elif line.startswith("-") and not line.startswith("---"):
                        print(colorize(line.rstrip("\r\n"), Colors.RED))
                    elif line.startswith("@@"):
                        print(colorize(line.rstrip("\r\n"), Colors.CYAN))
                    else:
                        print(line.rstrip("\r\n"))

                if not args.dry_run:
                    write_text_safely(
                        file_path,
                        new_content,
                        encoding=encoding if "lossy" not in encoding else "utf-8",
                        backup=args.backup,
                    )

    if args.dry_run:
        print_warning(
            f"\n[DRY RUN] Would replace {total_replacements} occurrence(s) across {total_files_matched} file(s)."
        )
    else:
        print_success(
            f"Successfully replaced {total_replacements} occurrence(s) across {total_files_matched} file(s)."
        )
    return 0


def cmd_dedup(args: argparse.Namespace) -> int:
    """Execute line deduplication command."""
    lines: List[str] = []
    if args.files:
        for file_arg in args.files:
            p = Path(file_arg)
            if p.is_file():
                content, _ = read_text_safely(p)
                lines.extend(content.splitlines())
            else:
                print_error(f"File not found: {file_arg}")
                return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print_info("Enter text to deduplicate (Ctrl+D or Ctrl+Z to finish):")
        lines = sys.stdin.read().splitlines()

    seen = {}
    ordered_unique = []

    for raw_line in lines:
        compare_line = raw_line
        if args.trim:
            compare_line = compare_line.strip()
        if args.ignore_case:
            compare_line = compare_line.lower()

        if compare_line not in seen:
            seen[compare_line] = 1
            ordered_unique.append(raw_line)
        else:
            seen[compare_line] += 1

    if args.sort:
        ordered_unique.sort(key=lambda s: s.lower() if args.ignore_case else s)

    out_lines = []
    for line in ordered_unique:
        compare_key = line.strip() if args.trim else line
        if args.ignore_case:
            compare_key = compare_key.lower()
        count_val = seen.get(compare_key, 1)
        if args.count:
            out_lines.append(f"{count_val:5d}  {line}")
        else:
            out_lines.append(line)

    result_text = "\n".join(out_lines)
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(result_text + "\n", encoding="utf-8")
        print_success(f"Deduplicated {len(lines)} lines -> {len(ordered_unique)} unique lines saved to {args.output}")
    else:
        if out_lines:
            print(result_text)

    return 0


def cmd_charset(args: argparse.Namespace) -> int:
    """Detect or convert character encodings."""
    table_rows = []

    for file_arg in args.files:
        p = Path(file_arg)
        files = find_files(p) if p.is_dir() else [p]

        for file_path in files:
            if not file_path.is_file():
                continue

            detected = detect_encoding(file_path)
            size_kb = f"{file_path.stat().st_size / 1024:.1f} KB"

            if args.convert:
                if detected.lower() == args.target_encoding.lower():
                    status = "Already " + args.target_encoding
                else:
                    try:
                        content, _ = read_text_safely(file_path, encodings=[detected])
                        write_text_safely(
                            file_path,
                            content,
                            encoding=args.target_encoding,
                            backup=args.backup,
                        )
                        status = f"Converted -> {args.target_encoding}"
                    except Exception as e:
                        status = f"Error: {e}"
                table_rows.append([str(file_path), detected, size_kb, status])
            else:
                table_rows.append([str(file_path), detected, size_kb, "Detected"])

    headers = ["File Path", "Encoding", "Size", "Action / Status"]
    print_table(headers, table_rows)
    return 0


def cmd_crlf(args: argparse.Namespace) -> int:
    """Normalize CRLF / LF line endings."""
    target_ending = b"\r\n" if args.to == "crlf" else b"\n"
    target_name = args.to.upper()
    modified_count = 0

    for path_arg in args.paths:
        p = Path(path_arg)
        files = find_files(p, include_patterns=args.glob_patterns) if p.is_dir() else [p]

        for file_path in files:
            if not file_path.is_file():
                continue

            try:
                raw_bytes = file_path.read_bytes()
            except Exception:
                continue

            # Check if binary (contains null bytes)
            if b"\x00" in raw_bytes[:4096]:
                continue

            # Normalize all to LF first, then to target
            normalized = raw_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            if target_ending == b"\r\n":
                normalized = normalized.replace(b"\n", b"\r\n")

            if normalized != raw_bytes:
                modified_count += 1
                if not args.dry_run:
                    file_path.write_bytes(normalized)
                print_info(f"Converted {file_path} to {target_name}")

    if args.dry_run:
        print_warning(f"[DRY RUN] Would convert {modified_count} file(s) to {target_name}.")
    else:
        print_success(f"Converted {modified_count} file(s) to {target_name}.")
    return 0
