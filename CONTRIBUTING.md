# Contributing to ScriptBox

Thank you for your interest in contributing to **ScriptBox**! We welcome contributions ranging from bug fixes to brand-new high-utility CLI scripts.

---

## Architecture Principles

1. **Standard Library First**: ScriptBox is designed to be ultra-fast, lightweight, and universally runnable across environments without requiring large dependency trees. Always favor Python's standard library (`pathlib`, `argparse`, `urllib`, `hashlib`, `secrets`, `difflib`, `socket`, `struct`, etc.) whenever possible.
2. **Modular Architecture**: All utilities reside inside `src/scriptbox/scripts/` grouped by domain.
3. **Dual Execution**: Scripts can be called both through the central `scriptbox <command>` dispatcher and imported as Python library modules.
4. **Structured Output**: Support human-friendly colorized console output (with table / bar visualizers) and `--json` for automation and piping.

---

## How to Add a New CLI Script in 3 Steps

### Step 1: Create or Select a Domain Module
Choose an existing module in `src/scriptbox/scripts/` (e.g. `text_tools.py`, `dev_tools.py`, `sys_tools.py`, `data_tools.py`, `net_tools.py`, `crypto_tools.py`, `media_tools.py`) or create a new one.

### Step 2: Implement the Command and Parser
In your module:
1. Define a command handler function `cmd_<tool_name>(args: argparse.Namespace) -> int`.
2. Register the argument parser in `register_subcommands(subparsers: argparse._SubParsersAction)`:

```python
def register_subcommands(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("my-tool", help="Short summary of tool.")
    p.add_argument("target", help="Target input.")
    p.add_argument("--json", action="store_true", help="Output JSON.")
    p.set_defaults(func=cmd_my_tool)

def cmd_my_tool(args: argparse.Namespace) -> int:
    # Implementation
    return 0
```

### Step 3: Add Unit Tests
Add corresponding unit tests in `tests/test_<module>.py` using `pytest`. Verify with:
```bash
pytest tests/ -v
```

---

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/bulsu-villamoraad/scriptbox.git
   cd scriptbox
   ```

2. Create virtual environment and install development dependencies:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate

   pip install -e ".[dev]"
   ```

3. Run the test suite:
   ```bash
   pytest tests/ -v
   ```

---

## Pull Request Guidelines

- Ensure your code passes all tests and linting.
- Add descriptive docstrings and comments.
- Keep commits atomic and clearly titled.
- Follow the PR template format.
