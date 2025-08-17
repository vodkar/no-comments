# shushpy/shushpy/cli.py
"""
Command-line interface for stripping comments and docstrings from Python code.

This CLI supports:
- Reading from stdin and writing the stripped result to stdout
- Processing one or more files or directories
- In-place rewriting for file and directory inputs
- Recursive directory traversal (configurable)

Usage examples:
- Single file to stdout:
    python -m shushpy.cli path/to/file.py
- From stdin to stdout:
    cat file.py | python -m shushpy.cli
- In-place, recursively on a directory:
    python -m shushpy.cli src/ --inplace
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Final

from shushpy import strip_comments, strip_path, strip_paths

logger: logging.Logger = logging.getLogger(__name__)

DEFAULT_ENCODING: Final[str] = "utf-8"
EXIT_SUCCESS: Final[int] = 0
EXIT_FAILURE: Final[int] = 1
EXIT_USAGE: Final[int] = 2


def _configure_logging(level: str) -> None:
    """Configure logging for the CLI.

    Args:
        level: Logging level name (e.g., 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG').
    """
    numeric_level: int = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser.

    Returns:
        The configured ArgumentParser.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="shushpy",
        description="Remove all comments and docstrings from Python code.",
    )

    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to process. If omitted, read from stdin and write to stdout.",
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Rewrite files in place. Required for multiple-file outputs.",
    )
    parser.add_argument(
        "--encoding",
        default=DEFAULT_ENCODING,
        help=f"Text encoding for reading/writing files (default: {DEFAULT_ENCODING}).",
    )
    parser.add_argument(
        "--recursive",
        dest="recursive",
        action="store_true",
        default=True,
        help="Recurse into subdirectories (default: enabled).",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Disable recursion when processing directories.",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        default="WARNING",
        help="Set the logging level (default: WARNING).",
    )
    return parser


def _process_stdin(encoding: str) -> int:
    """Read Python code from stdin, strip comments/docstrings, write to stdout.

    Args:
        encoding: Text encoding (informational; stdin/stdout typically handle text streams).

    Returns:
        Process exit code.
    """
    # Note: stdin/stdout are text streams; encoding parameter is informational for symmetry.
    try:
        input_text: str = sys.stdin.read()
        output_text: str = strip_comments(input_text)
        written: int = sys.stdout.write(output_text)
        # Ensure flush to avoid buffering surprises in pipelines.
        sys.stdout.flush()
        logger.debug("Wrote %d bytes to stdout", written)
        return EXIT_SUCCESS
    except SyntaxError:
        logger.exception("Failed to parse Python code from stdin due to a syntax error")
        return EXIT_FAILURE
    except ValueError as exc:
        logger.exception("Invalid stdin input: %s", exc)
        return EXIT_FAILURE
    except OSError:
        logger.exception("I/O error while writing to stdout")
        return EXIT_FAILURE


def _process_paths(
    paths: list[str],
    *,
    inplace: bool,
    encoding: str,
    recursive: bool,
) -> int:
    """Process one or more filesystem paths.

    Args:
        paths: Paths to files or directories.
        inplace: If True, rewrite files in place.
        encoding: Encoding used when reading/writing files.
        recursive: Whether to traverse directories recursively.

    Returns:
        Process exit code.
    """
    if not paths:
        logger.error("No paths provided")
        return EXIT_USAGE

    try:
        if inplace:
            results: dict[str, str] = strip_paths(
                [Path(p) for p in paths],
                inplace=True,
                encoding=encoding,
                recursive=recursive,
            )
            logger.info("Processed %d file(s) in place", len(results))
            return EXIT_SUCCESS

        # Not inplace: emit to stdout only when there is exactly one output.
        # We allow a single file or a directory that resolves to exactly one .py file.
        single_results: dict[str, str] = strip_path(
            Path(paths[0]),
            inplace=False,
            encoding=encoding,
            recursive=recursive,
        )
        if len(single_results) != 1:
            logger.error(
                "Refusing to write multiple files to stdout. "
                "Use --inplace for multi-file outputs or provide a single file."
            )
            return EXIT_USAGE

        only_item: tuple[str, str] = next(iter(single_results.items()))
        only_path: str
        only_content: str
        only_path, only_content = only_item
        logger.debug("Writing result for %s to stdout", only_path)
        written: int = sys.stdout.write(only_content)
        sys.stdout.flush()
        logger.debug("Wrote %d bytes to stdout", written)
        return EXIT_SUCCESS

    except FileNotFoundError:
        logger.exception("One or more paths do not exist")
        return EXIT_FAILURE
    except ValueError as exc:
        logger.exception("Invalid input paths: %s", exc)
        return EXIT_FAILURE
    except SyntaxError:
        logger.exception("Syntax error encountered while processing files")
        return EXIT_FAILURE
    except OSError:
        logger.exception("Filesystem error while processing files")
        return EXIT_FAILURE


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments; if None, defaults to sys.argv[1:].

    Returns:
        Process exit code.
    """
    args: argparse.Namespace = _build_parser().parse_args(argv)
    _configure_logging(args.log_level)

    path_args: list[str] = list(args.paths)
    inplace: bool = bool(args.inplace)
    encoding: str = str(args.encoding)
    recursive: bool = bool(args.recursive)

    if not path_args:
        if inplace:
            logger.error("--inplace cannot be used when reading from stdin")
            return EXIT_USAGE
        return _process_stdin(encoding=encoding)

    return _process_paths(
        path_args, inplace=inplace, encoding=encoding, recursive=recursive
    )


if __name__ == "__main__":
    sys.exit(main())
