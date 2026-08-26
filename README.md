# 🧰 ScriptBox

[![CI](https://github.com/bulsu-villamoraad/scriptbox/actions/workflows/ci.yml/badge.svg)](https://github.com/bulsu-villamoraad/scriptbox/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero Heavy Dependencies](https://img.shields.io/badge/dependencies-zero%20required-brightgreen.svg)](#features)

**ScriptBox** is a modular, high-utility collection of small, robust, and handy Python CLI utilities and scripts. Built standard-library-first, it requires zero mandatory external dependencies and delivers fast, reliable tooling across Windows, Linux, and macOS.

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/bulsu-villamoraad/scriptbox.git
cd scriptbox

# Install in editable mode
pip install -e .

# Or run instantly with uv / pipx
uv run scriptbox --help
```

---

## 🛠️ Tool Suite Catalog

ScriptBox provides **23 built-in commands** organized into 7 functional domains:

| Category | Command | Description |
| :--- | :--- | :--- |
| **Text & Files** | `replace` | Bulk regex/string find-and-replace across directories with colored diff preview and backup. |
| | `dedup` | Deduplicate lines in files or stdin while preserving order, with sort and frequency counts. |
| | `charset` | Detect and convert file encodings (UTF-8, Latin-1, CP1252, UTF-16, ASCII). |
| | `crlf` | Normalize line endings across source code (LF <-> CRLF). |
| **Developer & Code** | `scan-secrets` | Audit codebases for leaked API keys, tokens (AWS, OpenAI, GitHub, Slack), and private keys. |
| | `todos` | Extract and aggregate `TODO`, `FIXME`, `BUG`, and `NOTE` comments with Markdown/JSON export. |
| | `license-check` | Validate and inject copyright and license headers across source files. |
| **System & Diagnostics** | `disk-usage` | Visualize disk space consumption with progress bars and top-N rankings. |
| | `port-info` | Identify listening TCP/UDP ports and owning process IDs/names across platforms. |
| | `purge-cache` | Safely clean up `__pycache__`, `.pytest_cache`, `.DS_Store`, `Thumbs.db`, and `.tmp` files. |
| **Data & Serialization** | `convert` | Transform structured files between JSON, CSV, TSV, YAML, TOML, and XML. |
| | `json-diff` | Semantically compare structured JSON/YAML datasets highlighting added/removed/modified keys. |
| | `flatten` | Flatten deeply nested JSON objects to dot-notation keys or tabular CSV. |
| **Network & Web** | `http` | Lightweight HTTP client with latency breakdown, response header inspection, and JSON formatting. |
| | `port-scan` | Fast multithreaded TCP port scanner for host reconnaissance and connectivity checks. |
| | `trace-url` | Trace HTTP/HTTPS redirect chains (301, 302, 307, 308) and display each hop. |
| | `download` | Resumable file downloader with live progress bar and SHA-256 integrity verification. |
| **Security & Crypto** | `hash` | Compute and verify cryptographic checksums (SHA256, MD5, SHA512, BLAKE2b) and manifest files. |
| | `passgen` | Generate cryptographically secure passwords and Diceware passphrases with Shannon entropy scores. |
| | `jwt-decode` | Decode, inspect payload claims, and validate expiration times of JSON Web Tokens. |
| | `b64` | Encode and decode Base64, URL-safe Base64, and Hex data. |
| **Media & Privacy** | `exif` | Inspect and strip private EXIF / GPS metadata tags from JPEG/PNG images. |
| | `img-info` | Inspect image dimensions (width, height) and format directly from file headers. |

---

## 📖 Usage Examples

### 1. Text & File Manipulation
```bash
# Find and replace regex across all Python files with diff preview (dry run)
scriptbox replace "old_api\(\)" "new_api()" src/ --glob "*.py" --dry-run

# Deduplicate lines and show counts
cat emails.txt | scriptbox dedup --count --sort

# Convert Windows CRLF newlines to Unix LF across the project
scriptbox crlf src/ --to lf
```

### 2. Developer & Code Hygiene
```bash
# Scan repository for accidental secret leaks before committing
scriptbox scan-secrets . --fail-on-found

# Extract all TODOs and export as a Markdown checklist
scriptbox todos src/ --format markdown > TODO_LIST.md

# Ensure all source files contain license headers
scriptbox license-check src/ --holder "BulSU Team" --inject
```

### 3. System Diagnostics
```bash
# Inspect top 10 largest folders/files with usage bars
scriptbox disk-usage . --top 10

# Find out what service is running on port 8080
scriptbox port-info 8080

# Clean up all python caches and temporary build files
scriptbox purge-cache .
```

### 4. Data Conversion & Diff
```bash
# Convert JSON array to CSV
scriptbox convert users.json --to csv -o users.csv

# Semantically diff two configuration files
scriptbox json-diff config.v1.json config.v2.json

# Flatten nested JSON object
scriptbox flatten nested.json
```

### 5. Network & HTTP Diagnostics
```bash
# Make HTTP request with latency timing and response headers
scriptbox http https://api.github.com/zen -i

# Scan local ports
scriptbox port-scan localhost -p 80,443,3000,5432,8080

# Trace URL shortener redirect chain
scriptbox trace-url https://bit.ly/example
```

### 6. Security & Cryptography
```bash
# Compute SHA256 checksum
scriptbox hash myfile.zip -a sha256

# Verify integrity against a checksums manifest
scriptbox hash --check checksums.sha256

# Generate a 20-character high-entropy password
scriptbox passgen -l 20

# Generate a 4-word Diceware passphrase
scriptbox passgen -w 4 -s "-"

# Decode and validate a JWT
scriptbox jwt-decode "eyJhbGciOiJIUzI1NiIsIn..."
```

### 7. Media & Privacy
```bash
# Strip GPS and camera EXIF metadata before sharing photos
scriptbox exif photo.jpg --strip --backup

# Quick inspect image dimensions
scriptbox img-info assets/
```

---

## 🧪 Testing

ScriptBox comes with a comprehensive test suite covering all modules:

```bash
# Run all tests
pytest tests/ -v

# Run with test coverage
pytest --cov=scriptbox tests/
```

---

## 📂 Project Architecture

```
scriptbox/
├── .github/
│   ├── workflows/ci.yml       # Multi-OS & Multi-Python CI matrix
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/
├── src/
│   └── scriptbox/
│       ├── __init__.py        # Version and package metadata
│       ├── cli.py             # Central CLI dispatcher
│       ├── utils/
│       │   ├── console.py     # ANSI colors, table formatting, progress
│       │   └── files.py       # Atomic writes, encoding detection, search
│       └── scripts/
│           ├── text_tools.py  # replace, dedup, charset, crlf
│           ├── dev_tools.py   # scan-secrets, todos, license-check
│           ├── sys_tools.py   # disk-usage, port-info, purge-cache
│           ├── data_tools.py  # convert, json-diff, flatten
│           ├── net_tools.py   # http, port-scan, trace-url, download
│           ├── crypto_tools.py# hash, passgen, jwt-decode, b64
│           └── media_tools.py # exif, img-info
├── tests/                     # Full pytest test suite
├── pyproject.toml             # Modern packaging standard
├── CONTRIBUTING.md            # Contributor guidelines
├── LICENSE                    # MIT License
└── README.md
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).

Author: **Arvin Aidrian D. Villamor** (<2022100502@ms.bulsu.edu.ph>)
