#!/usr/bin/env python3
"""A CLI tool that counts words, lines, and characters in files.

Uses argparse for argument parsing. Mimics the Unix `wc` command.

Usage:
    python wc_tool.py file.txt
    python wc_tool.py file1.txt file2.txt
    python wc_tool.py -l file.txt          # lines only
    python wc_tool.py -w file.txt          # words only
    python wc_tool.py -c file.txt          # chars only
    echo "hello world" | python wc_tool.py  # read from stdin
"""

import argparse
import sys
from pathlib import Path


def count_text(text: str) -> dict[str, int]:
    """Count lines, words, and characters in a string.

    Args:
        text: The input string to analyze.

    Returns:
        Dict with keys 'lines', 'words', 'chars'.
    """
    return {
        "lines": text.count("\n"),
        "words": len(text.split()),
        "chars": len(text),
    }


def format_counts(counts: dict[str, int], show_lines: bool, show_words: bool,
                   show_chars: bool, label: str) -> str:
    """Format counts into a wc-style output line.

    Args:
        counts: Dict with 'lines', 'words', 'chars' keys.
        show_lines: Include line count in output.
        show_words: Include word count in output.
        show_chars: Include character count in output.
        label: Filename or 'total' to append.

    Returns:
        Formatted string like '       5      10      42 file.txt'.
    """
    parts = []
    if show_lines:
        parts.append(f"{counts['lines']:>8}")
    if show_words:
        parts.append(f"{counts['words']:>8}")
    if show_chars:
        parts.append(f"{counts['chars']:>8}")
    if label:
        parts.append(f" {label}")
    return "".join(parts)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Count lines, words, and characters in files (like wc)."
    )
    parser.add_argument(
        "-l", "--lines",
        action="store_true",
        help="Show line count only.",
    )
    parser.add_argument(
        "-w", "--words",
        action="store_true",
        help="Show word count only.",
    )
    parser.add_argument(
        "-c", "--chars",
        action="store_true",
        help="Show character count only.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to analyze. Reads from stdin if none given.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # If no flags given, show all three
    show_lines = args.lines or not (args.lines or args.words or args.chars)
    show_words = args.words or not (args.lines or args.words or args.chars)
    show_chars = args.chars or not (args.lines or args.words or args.chars)

    # Read from stdin if no files provided
    if not args.files:
        text = sys.stdin.read()
        counts = count_text(text)
        print(format_counts(counts, show_lines, show_words, show_chars, ""))
        return

    totals = {"lines": 0, "words": 0, "chars": 0}
    multiple = len(args.files) > 1

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"wc_tool: {filepath}: No such file", file=sys.stderr)
            continue

        text = path.read_text(encoding="utf-8")
        counts = count_text(text)
        print(format_counts(counts, show_lines, show_words, show_chars, filepath))

        for key in totals:
            totals[key] += counts[key]

    if multiple:
        print(format_counts(totals, show_lines, show_words, show_chars, "total"))


if __name__ == "__main__":
    main()
