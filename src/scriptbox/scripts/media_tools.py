"""Media and image inspection/privacy utilities: exif, img-info."""

import argparse
import os
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scriptbox.utils.console import (
    format_bytes,
    output_json_or_text,
    print_error,
    print_header,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from scriptbox.utils.files import find_files


def register_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register media inspection subcommands."""

    # 1. exif
    p_exif = subparsers.add_parser(
        "exif",
        help="Inspect or strip EXIF metadata (camera, GPS, timestamp) from image files.",
        description="View or remove private EXIF and location tags from JPEG, PNG, and TIFF images.",
    )
    p_exif.add_argument("images", nargs="+", help="Image file paths to inspect or sanitize.")
    p_exif.add_argument("-s", "--strip", action="store_true", help="Strip all EXIF/metadata tags for privacy protection.")
    p_exif.add_argument("-b", "--backup", action="store_true", help="Create a .bak backup before stripping metadata.")
    p_exif.add_argument("--json", action="store_true", help="Output metadata tags as JSON.")
    p_exif.set_defaults(func=cmd_exif)

    # 2. img-info
    p_info = subparsers.add_parser(
        "img-info",
        help="Display image dimensions (width, height), color type, and format without heavy dependencies.",
        description="Inspect image file header metadata (PNG, JPEG, GIF, BMP, WebP) directly.",
    )
    p_info.add_argument("images", nargs="+", help="Image files or directories to inspect.")
    p_info.add_argument("--json", action="store_true", help="Output dimensions as JSON.")
    p_info.set_defaults(func=cmd_img_info)


def get_image_info(path: Path) -> Optional[Dict[str, Any]]:
    """Parse image dimensions and format from binary headers."""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
            size = path.stat().st_size

            # PNG
            if head.startswith(b"\x89PNG\r\n\x1a\n"):
                w, h = struct.unpack(">LL", head[16:24])
                return {"format": "PNG", "width": w, "height": h, "size_bytes": size, "path": str(path)}

            # GIF
            if head[:6] in (b"GIF87a", b"GIF89a"):
                w, h = struct.unpack("<HH", head[6:10])
                return {"format": "GIF", "width": w, "height": h, "size_bytes": size, "path": str(path)}

            # BMP
            if head.startswith(b"BM"):
                w, h = struct.unpack("<ll", head[18:26])
                return {"format": "BMP", "width": abs(w), "height": abs(h), "size_bytes": size, "path": str(path)}

            # WebP
            if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
                if head[12:16] == b"VP8 ":
                    w, h = struct.unpack("<HH", head[26:30])
                    return {"format": "WebP", "width": w & 0x3FFF, "height": h & 0x3FFF, "size_bytes": size, "path": str(path)}
                elif head[12:16] == b"VP8L":
                    b0, b1, b2, b3 = head[21:25]
                    w = 1 + (((b1 & 0x3F) << 8) | b0)
                    h = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
                    return {"format": "WebP (Lossless)", "width": w, "height": h, "size_bytes": size, "path": str(path)}
                elif head[12:16] == b"VP8X":
                    w = 1 + struct.unpack("<I", head[24:27] + b"\x00")[0]
                    h = 1 + struct.unpack("<I", head[27:30] + b"\x00")[0]
                    return {"format": "WebP (Extended)", "width": w, "height": h, "size_bytes": size, "path": str(path)}

            # JPEG
            if head.startswith(b"\xff\xd8"):
                f.seek(0)
                f.read(2)
                while True:
                    marker_bytes = f.read(2)
                    if not marker_bytes or len(marker_bytes) < 2:
                        break
                    marker, = struct.unpack(">H", marker_bytes)
                    if marker in (0xFFC0, 0xFFC1, 0xFFC2):  # SOF markers
                        f.read(3)  # length & precision
                        h, w = struct.unpack(">HH", f.read(4))
                        return {"format": "JPEG", "width": w, "height": h, "size_bytes": size, "path": str(path)}
                    elif marker == 0xFFDA or marker == 0xFFD9:  # SOS or EOI
                        break
                    elif 0xFFE0 <= marker <= 0xFFEF or marker in (0xFFDB, 0xFFC4, 0xFFDD, 0xFFFE):
                        length, = struct.unpack(">H", f.read(2))
                        f.seek(length - 2, 1)
                    else:
                        break
                return {"format": "JPEG", "width": "Unknown", "height": "Unknown", "size_bytes": size, "path": str(path)}

    except Exception:
        pass
    return None


def strip_jpeg_exif(path: Path, backup: bool = False) -> bool:
    """Remove APP1 (EXIF) segment from JPEG file."""
    try:
        raw = path.read_bytes()
        if not raw.startswith(b"\xff\xd8"):
            return False

        if backup:
            path.with_name(f"{path.name}.bak").write_bytes(raw)

        # Rebuild JPEG omitting APP1 (0xFFE1)
        out = bytearray(b"\xff\xd8")
        idx = 2
        while idx < len(raw) - 1:
            if raw[idx] != 0xFF:
                out.extend(raw[idx:])
                break
            marker = raw[idx + 1]
            if marker == 0xDA:  # Start of Scan (image data)
                out.extend(raw[idx:])
                break
            if marker in (0xD8, 0xD9):  # SOI, EOI
                out.extend(raw[idx:idx + 2])
                idx += 2
                continue

            length = (raw[idx + 2] << 8) + raw[idx + 3]
            segment = raw[idx: idx + 2 + length]

            if marker == 0xE1:  # APP1 (EXIF / XMP)
                pass  # Skip EXIF segment
            else:
                out.extend(segment)

            idx += 2 + length

        path.write_bytes(bytes(out))
        return True
    except Exception as e:
        print_error(f"Error stripping EXIF from {path}: {e}")
        return False


def cmd_exif(args: argparse.Namespace) -> int:
    """Inspect or strip EXIF metadata."""
    for img_arg in args.images:
        p = Path(img_arg)
        if not p.is_file():
            print_error(f"File not found: {img_arg}")
            continue

        if args.strip:
            if p.suffix.lower() in (".jpg", ".jpeg"):
                success = strip_jpeg_exif(p, backup=args.backup)
                if success:
                    print_success(f"Sanitized EXIF metadata from {p}")
                else:
                    print_warning(f"Could not strip EXIF from {p}")
            else:
                print_warning(f"Stripping currently supported for JPEG images. ({p.name})")
        else:
            # Inspection
            info = get_image_info(p)
            raw = p.read_bytes()
            has_exif = b"Exif" in raw[:2048]
            has_gps = b"GPS" in raw[:4096]

            data = {
                "file": str(p),
                "format": info["format"] if info else p.suffix.upper().lstrip("."),
                "dimensions": f"{info['width']}x{info['height']}" if info else "Unknown",
                "file_size": format_bytes(p.stat().st_size),
                "has_exif_tags": has_exif,
                "has_gps_coordinates": has_gps,
            }

            if args.json:
                output_json_or_text(data, as_json=True)
            else:
                print_header(f"Image Metadata: {p.name}")
                for k, v in data.items():
                    print(f"  {k:20}: {v}")

    return 0


def cmd_img_info(args: argparse.Namespace) -> int:
    """Display image dimensions and properties."""
    results: List[Dict[str, Any]] = []

    for img_arg in args.images:
        p = Path(img_arg)
        files = find_files(p) if p.is_dir() else [p]

        for file_path in files:
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
                info = get_image_info(file_path)
                if info:
                    results.append(info)

    if args.json:
        output_json_or_text(results, as_json=True)
        return 0

    if results:
        print_header(f"Image Inspection Results ({len(results)} images)")
        rows = [
            [r["path"], r["format"], f"{r['width']} x {r['height']}", format_bytes(r["size_bytes"])]
            for r in results
        ]
        print_table(["File", "Format", "Dimensions (W x H)", "Size"], rows)
    else:
        print_info("No supported image files found.")

    return 0
