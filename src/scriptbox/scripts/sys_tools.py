"""System diagnostic and maintenance tools: disk-usage, port-info, purge-cache."""

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scriptbox.utils.console import (
    Colors,
    colorize,
    format_bytes,
    output_json_or_text,
    print_error,
    print_header,
    print_info,
    print_success,
    print_table,
    print_warning,
)


PURGE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    ".DS_Store",
    "Thumbs.db",
    "*.tmp",
    "*~",
    "*.bak",
]


def register_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register system tool subcommands."""

    # 1. disk-usage
    p_du = subparsers.add_parser(
        "disk-usage",
        help="Analyze disk space usage and identify largest files and folders.",
        description="Inspect directory sizes, sort by disk consumption, and visualize with progress bars.",
    )
    p_du.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to analyze (default: current directory).",
    )
    p_du.add_argument(
        "-n",
        "--top",
        type=int,
        default=10,
        help="Number of largest entries to display (default: 10).",
    )
    p_du.add_argument(
        "--files-only",
        action="store_true",
        help="Only rank individual files, ignoring directories.",
    )
    p_du.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    p_du.set_defaults(func=cmd_disk_usage)

    # 2. port-info
    p_port = subparsers.add_parser(
        "port-info",
        help="Check which process or application is listening on network ports.",
        description="Identify listening TCP/UDP ports and owning process IDs across Windows, macOS, and Linux.",
    )
    p_port.add_argument(
        "port",
        type=int,
        nargs="?",
        help="Specific port number to inspect (if omitted, lists all listening ports).",
    )
    p_port.add_argument(
        "--json",
        action="store_true",
        help="Output port listening data as JSON.",
    )
    p_port.set_defaults(func=cmd_port_info)

    # 3. purge-cache
    p_purge = subparsers.add_parser(
        "purge-cache",
        help="Clean up cache artifacts, __pycache__, .pytest_cache, and temporary files.",
        description="Safely purge build and runtime cache files to free disk space.",
    )
    p_purge.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Directories to clean (default: current directory).",
    )
    p_purge.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Preview files and folders that would be deleted without deleting.",
    )
    p_purge.set_defaults(func=cmd_purge_cache)


def get_dir_size(path: Path) -> int:
    """Calculate recursive size of a directory in bytes."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_dir_size(Path(entry.path))
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except (PermissionError, FileNotFoundError, OSError):
        pass
    return total


def cmd_disk_usage(args: argparse.Namespace) -> int:
    """Analyze disk consumption."""
    target = Path(args.path).resolve()
    if not target.exists():
        print_error(f"Path does not exist: {target}")
        return 1

    entries: List[Tuple[str, int, bool]] = []  # (name/path, size_bytes, is_dir)

    if target.is_file():
        entries.append((str(target), target.stat().st_size, False))
    else:
        try:
            for item in target.iterdir():
                try:
                    if item.is_file():
                        entries.append((item.name, item.stat().st_size, False))
                    elif item.is_dir() and not args.files_only:
                        size = get_dir_size(item)
                        entries.append((f"{item.name}/", size, True))
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError) as e:
            print_error(f"Cannot read directory {target}: {e}")
            return 1

    entries.sort(key=lambda x: x[1], reverse=True)
    top_entries = entries[: args.top]
    max_size = top_entries[0][1] if top_entries else 1

    if args.json:
        data = [
            {"path": name, "size_bytes": size, "is_directory": is_dir, "human_size": format_bytes(size)}
            for name, size, is_dir in top_entries
        ]
        output_json_or_text(data, as_json=True)
        return 0

    print_header(f"Disk Usage Breakdown: {target} (Top {len(top_entries)})")
    table_rows = []
    bar_width = 20

    for name, size, is_dir in top_entries:
        ratio = size / max_size if max_size > 0 else 0
        filled = int(round(ratio * bar_width))
        bar = "[" + "#" * filled + " " * (bar_width - filled) + "]"
        type_str = "DIR" if is_dir else "FILE"
        table_rows.append([type_str, name, format_bytes(size), bar])

    print_table(["Type", "Name", "Size", "Relative Usage"], table_rows)
    return 0


def cmd_port_info(args: argparse.Namespace) -> int:
    """List or inspect listening network ports."""
    results: List[Dict[str, Any]] = []

    if sys.platform == "win32":
        try:
            output = subprocess.check_output("netstat -ano -p tcp", shell=True, text=True)
            for line in output.splitlines():
                if "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        proto = parts[0]
                        local_addr = parts[1]
                        state = parts[3]
                        pid = parts[4]

                        # Extract port
                        port_str = local_addr.rsplit(":", 1)[-1]
                        if port_str.isdigit():
                            port_num = int(port_str)
                            if args.port and port_num != args.port:
                                continue

                            # Try to get process name
                            pname = "Unknown"
                            try:
                                task_out = subprocess.check_output(
                                    f'tasklist /FI "PID eq {pid}" /FO CSV /NH',
                                    shell=True,
                                    text=True,
                                    stderr=subprocess.DEVNULL,
                                )
                                if task_out.strip():
                                    pname = task_out.strip().split(",")[0].replace('"', '')
                            except Exception:
                                pass

                            results.append({
                                "proto": proto,
                                "local_address": local_addr,
                                "port": port_num,
                                "state": state,
                                "pid": pid,
                                "process_name": pname,
                            })
        except Exception as e:
            print_error(f"Failed to query netstat on Windows: {e}")
            return 1
    else:
        # Linux/macOS fallback using ss or lsof
        try:
            cmd = "ss -tlpn" if shutil.which("ss") else "lsof -iTCP -sTCP:LISTEN -n -P"
            output = subprocess.check_output(cmd, shell=True, text=True)
            for line in output.splitlines():
                if "LISTEN" in line:
                    results.append({"raw": line})
        except Exception:
            # Fallback socket test for specific port
            if args.port:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    is_open = s.connect_ex(("127.0.0.1", args.port)) == 0
                    results.append({
                        "proto": "TCP",
                        "local_address": f"127.0.0.1:{args.port}",
                        "port": args.port,
                        "state": "LISTENING" if is_open else "CLOSED",
                        "pid": "-",
                        "process_name": "-",
                    })

    if args.json:
        output_json_or_text(results, as_json=True)
        return 0

    if results:
        print_header("Active Listening Network Ports")
        if "process_name" in results[0]:
            rows = [
                [r["proto"], str(r["port"]), r["local_address"], r["pid"], r["process_name"], r["state"]]
                for r in results
            ]
            print_table(["Proto", "Port", "Address", "PID", "Process Name", "State"], rows)
        else:
            for r in results:
                print(r.get("raw", str(r)))
    else:
        if args.port:
            print_info(f"Port {args.port} is NOT currently in use.")
        else:
            print_info("No active listening ports discovered.")

    return 0


def cmd_purge_cache(args: argparse.Namespace) -> int:
    """Purge temporary and cache files."""
    cleaned_files = 0
    cleaned_dirs = 0
    freed_bytes = 0

    for path_arg in args.paths:
        target = Path(path_arg).resolve()
        if not target.exists():
            continue

        for root, dirs, files in os.walk(target, topdown=False):
            # Check directories (e.g. __pycache__, .pytest_cache)
            for d in list(dirs):
                d_path = Path(root) / d
                if d in ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov"):
                    size = get_dir_size(d_path)
                    freed_bytes += size
                    cleaned_dirs += 1
                    if not args.dry_run:
                        shutil.rmtree(d_path, ignore_errors=True)
                    print_info(f"{'[DRY RUN] Would delete' if args.dry_run else 'Deleted'} directory: {d_path} ({format_bytes(size)})")

            # Check files
            for f in files:
                f_path = Path(root) / f
                if f.endswith((".pyc", ".pyo", ".pyd", ".tmp", ".bak", "~")) or f in (".DS_Store", "Thumbs.db"):
                    try:
                        size = f_path.stat().st_size
                    except OSError:
                        size = 0
                    freed_bytes += size
                    cleaned_files += 1
                    if not args.dry_run:
                        try:
                            f_path.unlink()
                        except OSError:
                            pass
                    print_info(f"{'[DRY RUN] Would delete' if args.dry_run else 'Deleted'} file: {f_path} ({format_bytes(size)})")

    action = "Would reclaim" if args.dry_run else "Reclaimed"
    print_success(
        f"{action} {format_bytes(freed_bytes)} across {cleaned_dirs} directories and {cleaned_files} files."
    )
    return 0
