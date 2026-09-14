"""Command-line interface for TallyPrime MCP.

Commands
--------
tallyprime-mcp                 Run the MCP server over stdio.
tallyprime-mcp --version       Print the installed version.
tallyprime-mcp test-connection Check connectivity to TallyPrime and exit.
tallyprime-mcp config          Print the effective (non-secret) configuration.
"""

from __future__ import annotations

import argparse
import json
import sys

from tallyprime_mcp import __version__
from tallyprime_mcp.config import load_settings
from tallyprime_mcp.logging_config import configure_logging


def _cmd_run(_args: argparse.Namespace) -> int:
    from tallyprime_mcp.server import main as server_main

    server_main()
    return 0


def _cmd_test_connection(_args: argparse.Namespace) -> int:
    settings = load_settings()
    configure_logging(level=settings.log_level, log_dir=settings.log_dir, json_lines=settings.log_json)

    from tallyprime_mcp.tally.client import TallyClient

    with TallyClient(settings) as client:
        ok, message = client.test_connection()
    print(message)
    return 0 if ok else 1


def _cmd_config(_args: argparse.Namespace) -> int:
    settings = load_settings()
    payload = {
        "host": settings.host,
        "port": settings.port,
        "base_url": settings.base_url,
        "scheme": settings.scheme,
        "timeout_seconds": settings.timeout_seconds,
        "connect_timeout_seconds": settings.connect_timeout_seconds,
        "default_company": settings.default_company,
        "read_only": settings.read_only,
        "max_response_bytes": settings.max_response_bytes,
        "max_request_bytes": settings.max_request_bytes,
        "default_voucher_limit": settings.default_voucher_limit,
        "log_level": settings.log_level,
        "log_dir": str(settings.log_dir) if settings.log_dir else None,
        "log_json": settings.log_json,
        "expose_raw_xml_tool": settings.expose_raw_xml_tool,
    }
    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tallyprime-mcp",
        description="MCP server for read-only access to a local TallyPrime installation.",
    )
    parser.add_argument("--version", action="store_true", help="Print the version and exit.")

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the MCP server over stdio (also the default).")
    run_parser.set_defaults(func=_cmd_run)

    test_parser = subparsers.add_parser(
        "test-connection", help="Check whether TallyPrime is reachable and exit."
    )
    test_parser.set_defaults(func=_cmd_test_connection)

    config_parser = subparsers.add_parser("config", help="Print the effective configuration as JSON.")
    config_parser.set_defaults(func=_cmd_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"tallyprime-mcp {__version__}")
        return 0

    if not getattr(args, "command", None):
        # Default with no subcommand: run the MCP server, matching the
        # "tallyprime-mcp" invocation documented in README/docs.
        return _cmd_run(args)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
