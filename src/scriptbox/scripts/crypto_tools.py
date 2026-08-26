"""Security and cryptographic utilities: hash, passgen, jwt-decode, b64."""

import argparse
import base64
import datetime
import hashlib
import json
import math
import secrets
import string
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from scriptbox.utils.files import find_files, read_text_safely


DICEWARE_WORDS = [
    "correct", "horse", "battery", "staple", "galaxy", "quantum", "nebula", "cipher",
    "shadow", "falcon", "beacon", "summit", "timber", "canyon", "voyage", "vector",
    "aurora", "breeze", "castle", "desert", "echo", "frost", "garden", "harbor",
    "island", "jungle", "knight", "lagoon", "meadow", "oasis", "planet", "quasar",
    "river", "silver", "temple", "valley", "wizard", "zenith", "anchor", "bridge",
]


def register_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register cryptography subcommands."""

    # 1. hash
    p_hash = subparsers.add_parser(
        "hash",
        help="Compute and verify cryptographic checksums (SHA256, MD5, SHA512, BLAKE2b).",
        description="Calculate file or string hashes and generate/verify checksum manifest files.",
    )
    p_hash.add_argument("targets", nargs="*", help="File paths or strings to hash (reads stdin if omitted).")
    p_hash.add_argument("-a", "--algorithm", default="sha256", choices=["md5", "sha1", "sha256", "sha512", "blake2b"], help="Hash algorithm.")
    p_hash.add_argument("-s", "--string", dest="is_string", action="store_true", help="Treat target arguments directly as literal strings instead of file paths.")
    p_hash.add_argument("-c", "--check", help="Verify checksums against a manifest file (e.g. checksums.sha256).")
    p_hash.add_argument("--json", action="store_true", help="Output hash results as JSON.")
    p_hash.set_defaults(func=cmd_hash)

    # 2. passgen
    p_pass = subparsers.add_parser(
        "passgen",
        help="Generate cryptographically secure passwords and Diceware passphrases.",
        description="Create high-entropy passwords with custom length, character sets, and Shannon entropy analysis.",
    )
    p_pass.add_argument("-l", "--length", type=int, default=16, help="Password length in characters (default: 16).")
    p_pass.add_argument("-n", "--count", type=int, default=1, help="Number of passwords to generate (default: 1).")
    p_pass.add_argument("--no-symbols", action="store_true", help="Exclude special symbols/punctuation.")
    p_pass.add_argument("--no-digits", action="store_true", help="Exclude numeric digits.")
    p_pass.add_argument("-w", "--words", type=int, help="Generate a multi-word Diceware passphrase instead of a random string.")
    p_pass.add_argument("-s", "--separator", default="-", help="Separator for word passphrases (default: '-').")
    p_pass.set_defaults(func=cmd_passgen)

    # 3. jwt-decode
    p_jwt = subparsers.add_parser(
        "jwt-decode",
        help="Decode, inspect, and validate expiration of JSON Web Tokens (JWT).",
        description="Decode JWT header and payload claims without verifying signature.",
    )
    p_jwt.add_argument("token", nargs="?", help="JWT string to decode (reads stdin if omitted).")
    p_jwt.set_defaults(func=cmd_jwt_decode)

    # 4. b64
    p_b64 = subparsers.add_parser(
        "b64",
        help="Encode or decode Base64, URL-safe Base64, and Hex data.",
        description="Transform strings or binary files to and from Base64 or Hex encoding.",
    )
    p_b64.add_argument("data", nargs="?", help="Input string or file path (reads stdin if omitted).")
    p_b64.add_argument("-d", "--decode", action="store_true", help="Decode input rather than encode.")
    p_b64.add_argument("-u", "--url-safe", action="store_true", help="Use URL-safe Base64 alphabet.")
    p_b64.add_argument("--hex", action="store_true", help="Use Hexadecimal format instead of Base64.")
    p_b64.set_defaults(func=cmd_b64)


def compute_hash(data: bytes, algo_name: str) -> str:
    """Compute hash for bytes."""
    h = getattr(hashlib, algo_name.lower())()
    h.update(data)
    return h.hexdigest()


def compute_file_hash(file_path: Path, algo_name: str) -> str:
    """Stream file in chunks to compute hash."""
    h = getattr(hashlib, algo_name.lower())()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def cmd_hash(args: argparse.Namespace) -> int:
    """Execute hash generation or verification."""
    algo = args.algorithm.lower()

    if args.check:
        manifest = Path(args.check)
        if not manifest.is_file():
            print_error(f"Manifest file not found: {args.check}")
            return 1

        lines = manifest.read_text(encoding="utf-8").splitlines()
        passed = 0
        failed = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue

            expected_hash, rel_path = parts
            rel_path = rel_path.lstrip("* ")
            target_file = manifest.parent / rel_path

            if not target_file.is_file():
                print_error(f"{rel_path}: FAILED (file not found)")
                failed += 1
                continue

            actual_hash = compute_file_hash(target_file, algo)
            if actual_hash.lower() == expected_hash.lower():
                print_success(f"{rel_path}: OK")
                passed += 1
            else:
                print_error(f"{rel_path}: FAILED (Checksum mismatch)")
                failed += 1

        if failed == 0:
            print_success(f"\nAll {passed} files verified successfully.")
            return 0
        else:
            print_error(f"\nVerification finished: {passed} passed, {failed} failed.")
            return 1

    results: List[Dict[str, str]] = []

    if args.is_string:
        for text in args.targets:
            digest = compute_hash(text.encode("utf-8"), algo)
            results.append({"target": text, "type": "string", "hash": digest, "algo": algo.upper()})
    elif args.targets:
        for t in args.targets:
            p = Path(t)
            if p.is_file():
                digest = compute_file_hash(p, algo)
                results.append({"target": str(p), "type": "file", "hash": digest, "algo": algo.upper()})
            else:
                print_error(f"Target file not found: {t}")
    else:
        raw = sys.stdin.buffer.read()
        digest = compute_hash(raw, algo)
        results.append({"target": "<stdin>", "type": "stdin", "hash": digest, "algo": algo.upper()})

    if args.json:
        output_json_or_text(results, as_json=True)
        return 0

    for r in results:
        print(f"{r['hash']}  {r['target']}")

    return 0


def cmd_passgen(args: argparse.Namespace) -> int:
    """Generate passwords or passphrases."""
    passwords = []

    for _ in range(args.count):
        if args.words:
            chosen = [secrets.choice(DICEWARE_WORDS) for _ in range(args.words)]
            pwd = args.separator.join(chosen)
            pool_size = len(DICEWARE_WORDS)
            entropy = args.words * math.log2(pool_size)
        else:
            chars = string.ascii_letters
            if not args.no_digits:
                chars += string.digits
            if not args.no_symbols:
                chars += "!@#$%^&*()-_=+[]{}<>?"

            pwd = "".join(secrets.choice(chars) for _ in range(args.length))
            pool_size = len(chars)
            entropy = args.length * math.log2(pool_size)

        passwords.append((pwd, entropy))

    for pwd, ent in passwords:
        strength = "Very Strong" if ent >= 80 else "Strong" if ent >= 60 else "Moderate" if ent >= 40 else "Weak"
        color = Colors.GREEN if ent >= 60 else Colors.YELLOW if ent >= 40 else Colors.RED
        print(f"{pwd}  {colorize(f'[{ent:.1f} bits - {strength}]', color)}")

    return 0


def b64_decode_padded(s: str) -> bytes:
    """Decode base64 string with auto-padding."""
    s = s.strip()
    missing_padding = len(s) % 4
    if missing_padding:
        s += "=" * (4 - missing_padding)
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def cmd_jwt_decode(args: argparse.Namespace) -> int:
    """Decode and inspect JWT."""
    token = args.token or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
    if not token:
        print_error("No JWT token provided.")
        return 1

    parts = token.split(".")
    if len(parts) != 3:
        print_error("Invalid JWT format: A valid JWT consists of three dot-separated sections (Header.Payload.Signature).")
        return 1

    try:
        header = json.loads(b64_decode_padded(parts[0]))
        payload = json.loads(b64_decode_padded(parts[1]))
    except Exception as e:
        print_error(f"Failed to decode JWT base64/JSON: {e}")
        return 1

    print_header("JWT Header")
    print(json.dumps(header, indent=2))

    print_header("JWT Payload Claims")
    print(json.dumps(payload, indent=2))

    # Expiration analysis
    if "exp" in payload:
        exp_ts = payload["exp"]
        exp_dt = datetime.datetime.fromtimestamp(exp_ts, tz=datetime.timezone.utc)
        now_dt = datetime.datetime.now(tz=datetime.timezone.utc)
        is_expired = now_dt > exp_dt

        print_header("Token Expiration Analysis")
        print(f"  Expires At (UTC): {exp_dt.isoformat()}")
        if is_expired:
            diff = now_dt - exp_dt
            print_error(f"TOKEN IS EXPIRED (Expired {diff} ago)")
        else:
            diff = exp_dt - now_dt
            print_success(f"TOKEN IS VALID (Expires in {diff})")

    return 0


def cmd_b64(args: argparse.Namespace) -> int:
    """Encode / decode Base64 or Hex."""
    input_bytes = b""
    if args.data:
        p = Path(args.data)
        if p.is_file():
            input_bytes = p.read_bytes()
        else:
            input_bytes = args.data.encode("utf-8")
    else:
        input_bytes = sys.stdin.buffer.read()

    if args.decode:
        try:
            if args.hex:
                out_bytes = bytes.fromhex(input_bytes.decode("utf-8").strip())
            elif args.url_safe:
                out_bytes = b64_decode_padded(input_bytes.decode("utf-8"))
            else:
                out_bytes = base64.b64decode(input_bytes)

            try:
                print(out_bytes.decode("utf-8"))
            except UnicodeDecodeError:
                sys.stdout.buffer.write(out_bytes)
        except Exception as e:
            print_error(f"Decoding failed: {e}")
            return 1
    else:
        if args.hex:
            print(input_bytes.hex())
        elif args.url_safe:
            print(base64.urlsafe_b64encode(input_bytes).decode("utf-8"))
        else:
            print(base64.b64encode(input_bytes).decode("utf-8"))

    return 0
