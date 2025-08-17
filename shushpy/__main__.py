import sys
from typing import Final

from shushpy.cli import main as cli_main


def main(argv: list[str] | None = None) -> int:
    """Entrypoint delegating to the CLI main.

    Args:
        argv: Optional list of command-line arguments. If None, defaults to sys.argv[1:].

    Returns:
        Process exit code as an integer.
    """
    return cli_main(argv)


if __name__ == "__main__":
    EXIT_CODE: Final[int] = main()
    sys.exit(EXIT_CODE)
