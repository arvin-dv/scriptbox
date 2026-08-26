"""ScriptBox CLI Dispatcher and Central Entry Point."""

import argparse
import sys
from typing import List, Optional

from scriptbox import __version__
from scriptbox.scripts import (
    crypto_tools,
    data_tools,
    dev_tools,
    media_tools,
    net_tools,
    sys_tools,
    text_tools,
)
from scriptbox.utils.console import (
    Colors,
    colorize,
    print_error,
    print_header,
)


COMMAND_CATEGORIES = {
    "Text & Files": ["replace", "dedup", "charset", "crlf"],
    "Developer & Code": ["scan-secrets", "todos", "license-check"],
    "System & Diagnostics": ["disk-usage", "port-info", "purge-cache"],
    "Data & Formats": ["convert", "json-diff", "flatten"],
    "Network & Web": ["http", "port-scan", "trace-url", "download"],
    "Security & Crypto": ["hash", "passgen", "jwt-decode", "b64"],
    "Media & Privacy": ["exif", "img-info"],
}


class ScriptBoxArgumentParser(argparse.ArgumentParser):
    """Custom argument parser with grouped command display in help message."""

    def format_help(self) -> str:
        help_text = super().format_help()
        # Append categorization guide
        guide = [
            "",
            colorize("Available ScriptBox Tool Suites:", Colors.BOLD + Colors.CYAN),
        ]
        for cat, cmds in COMMAND_CATEGORIES.items():
            guide.append(f"  {colorize(cat + ':', Colors.BOLD + Colors.YELLOW)} {', '.join(cmds)}")
        guide.append("")
        guide.append("Run 'scriptbox <command> --help' for detailed instructions on any specific tool.")
        return help_text + "\n" + "\n".join(guide) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser and wire all module subcommands."""
    parser = ScriptBoxArgumentParser(
        prog="scriptbox",
        description="ScriptBox: A collection of small, handy, and robust Python CLI utilities and scripts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s v{__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        title="Commands",
        metavar="<command>",
    )

    # Register each suite
    text_tools.register_subcommands(subparsers)
    dev_tools.register_subcommands(subparsers)
    sys_tools.register_subcommands(subparsers)
    data_tools.register_subcommands(subparsers)
    net_tools.register_subcommands(subparsers)
    crypto_tools.register_subcommands(subparsers)
    media_tools.register_subcommands(subparsers)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main execution entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand or not hasattr(args, "func"):
        parser.print_help()
        return 0

    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        print_error("\nExecution interrupted by user.")
        return 130
    except Exception as e:
        print_error(f"Execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
