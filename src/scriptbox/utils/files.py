"""File system and I/O utility functions."""

import fnmatch
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator, List, Optional, Sequence, Tuple


DEFAULT_IGNORES = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    ".idea",
    ".vscode",
}

COMMON_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1", "utf-16", "ascii"]


def detect_encoding(file_path: Path) -> str:
    """Attempt to detect file encoding by trial reading chunks."""
    raw = file_path.read_bytes()[:65536]
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"

    for enc in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def read_text_safely(file_path: Path, encodings: Optional[Sequence[str]] = None) -> Tuple[str, str]:
    """Read text from a file, attempting several encodings if necessary.

    Returns (content, encoding_used).
    """
    candidates = list(encodings) if encodings else COMMON_ENCODINGS
    raw = file_path.read_bytes()

    for enc in candidates:
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue

    # Fallback with replacement
    return raw.decode("utf-8", errors="replace"), "utf-8 (lossy)"


def atomic_write(file_path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically write content to a file via a temporary file."""
    file_path = file_path.resolve()
    parent = file_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        dir=parent,
        delete=False,
        newline="",
    ) as tf:
        tf.write(content)
        temp_name = tf.name

    shutil.move(temp_name, file_path)


def write_text_safely(
    file_path: Path,
    content: str,
    encoding: str = "utf-8",
    backup: bool = False,
) -> Optional[Path]:
    """Write text to file with optional .bak backup creation.

    Returns backup Path if created.
    """
    backup_path = None
    if backup and file_path.exists():
        backup_path = file_path.with_name(f"{file_path.name}.bak")
        shutil.copy2(file_path, backup_path)

    atomic_write(file_path, content, encoding=encoding)
    return backup_path


def find_files(
    root: Path,
    include_patterns: Optional[Sequence[str]] = None,
    exclude_patterns: Optional[Sequence[str]] = None,
    max_depth: Optional[int] = None,
    skip_ignored_dirs: bool = True,
) -> Generator[Path, None, None]:
    """Recursively search for files matching inclusion/exclusion glob patterns."""
    root = root.resolve()
    if not root.exists():
        return

    if root.is_file():
        yield root
        return

    root_depth = len(root.parts)

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        current_depth = len(current_dir.parts) - root_depth

        if max_depth is not None and current_depth >= max_depth:
            dirnames.clear()
            continue

        if skip_ignored_dirs:
            dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORES and not d.startswith(".")]

        for filename in filenames:
            file_path = current_dir / filename

            # Check exclusions
            if exclude_patterns:
                if any(fnmatch.fnmatch(filename, pat) or fnmatch.fnmatch(str(file_path), pat) for pat in exclude_patterns):
                    continue

            # Check inclusions
            if include_patterns:
                if not any(fnmatch.fnmatch(filename, pat) or fnmatch.fnmatch(str(file_path), pat) for pat in include_patterns):
                    continue

            yield file_path
