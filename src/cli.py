from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path

from .orchestrator import Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OSINT Research Pipeline — AI-driven multi-source intelligence gathering",
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Research query to process",
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        help="Read query from file",
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        help="Path to config file (default: config/default.yaml)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    parser.add_argument(
        "pipeline_args",
        nargs=argparse.REMAINDER,
        help="Additional pipeline arguments (unused)",
    )
    return parser


async def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.file:
        query = Path(args.file).read_text().strip()
    elif args.query:
        query = args.query
    else:
        query = sys.stdin.read().strip()

    if not query:
        parser.print_help()
        return 1

    pipeline = Pipeline(config_path=args.config)

    try:
        result = await pipeline.run(query)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130

    output = pipeline.result_to_dict(result)
    indent = 2 if args.pretty else None

    if result.errors:
        output["errors"] = result.errors
        for err in result.errors:
            print(f"ERROR: {err}", file=sys.stderr)

    serialized = json.dumps(output, indent=indent, default=str, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(serialized, encoding="utf-8")
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(serialized)

    return 0 if not result.errors else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
