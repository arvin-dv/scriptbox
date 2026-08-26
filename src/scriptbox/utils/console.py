"""Terminal and console output formatting helpers."""

import json
import os
import sys
from typing import Any, List, Optional, Sequence


class Colors:
    """ANSI color escape codes."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def supports_color() -> bool:
    """Check if the current terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR") or os.environ.get("SCRIPTBOX_NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        # Check if Windows VT100 support is enabled
        return (
            os.environ.get("WT_SESSION") is not None
            or os.environ.get("ANSICON") is not None
            or os.environ.get("TERM") in ("xterm", "xterm-256color", "cygwin")
            or hasattr(os, "get_terminal_size")
        )
    return True


def colorize(text: str, color: str) -> str:
    """Wrap text with color if color is supported, otherwise return text as is."""
    if supports_color():
        return f"{color}{text}{Colors.RESET}"
    return text


def print_info(msg: str) -> None:
    """Print an informational message in cyan."""
    print(colorize(f"[*] {msg}", Colors.CYAN))


def print_success(msg: str) -> None:
    """Print a success message in green."""
    print(colorize(f"[+] {msg}", Colors.GREEN))


def print_warning(msg: str) -> None:
    """Print a warning message in yellow to stderr."""
    print(colorize(f"[!] {msg}", Colors.YELLOW), file=sys.stderr)


def print_error(msg: str) -> None:
    """Print an error message in red to stderr."""
    print(colorize(f"[-] {msg}", Colors.RED), file=sys.stderr)


def print_header(title: str) -> None:
    """Print a prominent section header."""
    separator = "=" * len(title)
    print(colorize(f"\n{separator}\n{title}\n{separator}", Colors.BOLD + Colors.BLUE))


def format_bytes(size_bytes: int) -> str:
    """Format bytes into a human-readable string (KB, MB, GB, etc.)."""
    if size_bytes < 0:
        return f"{size_bytes} B"
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:3.1f} {unit}" if unit != "B" else f"{int(size_bytes)} B"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} EB"


def format_duration(seconds: float) -> str:
    """Format a duration in seconds into a human-readable string."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f} µs"
    if seconds < 1.0:
        return f"{seconds * 1000:.1f} ms"
    if seconds < 60.0:
        return f"{seconds:.2f} s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {sec:.1f}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {sec:.0f}s"


def print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    align: Optional[Sequence[str]] = None,
) -> None:
    """Print a cleanly formatted ASCII table with headers and borders."""
    if not headers and not rows:
        return

    # Convert all cells to strings
    str_rows = [[str(cell) for cell in row] for row in rows]
    str_headers = [str(h) for h in headers]

    col_count = len(str_headers) if str_headers else max((len(r) for r in str_rows), default=0)
    if col_count == 0:
        return

    col_widths = [len(h) for h in str_headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))
            else:
                col_widths.append(len(cell))

    # Pad col_widths if necessary
    while len(col_widths) < col_count:
        col_widths.append(8)

    alignments = list(align) if align else ["<"] * col_count
    while len(alignments) < col_count:
        alignments.append("<")

    # Build border line
    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"

    print(sep)
    if str_headers:
        header_cells = [
            f"{h:{alignments[i]}{col_widths[i]}}"
            for i, h in enumerate(str_headers)
        ]
        print("| " + " | ".join(header_cells) + " |")
        print(sep)

    for row in str_rows:
        row_cells = []
        for i in range(col_count):
            val = row[i] if i < len(row) else ""
            row_cells.append(f"{val:{alignments[i]}{col_widths[i]}}")
        print("| " + " | ".join(row_cells) + " |")

    print(sep)


def output_json_or_text(data: Any, as_json: bool = False) -> None:
    """Utility to print JSON if requested, else formatted Python object representation."""
    if as_json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(data)
