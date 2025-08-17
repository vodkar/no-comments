# shushpy

Remove all comments and docstrings from Python code using a safe AST-based transform.

- Inline comments (e.g., `# comment`) are dropped.
- Module/class/function docstrings are removed.
- The code is re-generated via `ast.unparse`, so formatting may change, but semantics are preserved.

Python 3.12+ required. Zero third-party dependencies.

## Why this exists

- You need to distribute or compare Python sources without any comments or docstrings.
- You want a robust approach that won’t break on edge-case syntax or string tricks—AST transformations operate on parsed code, not raw text, so it’s resilient.

## Installation and usage with uv

Prerequisites:
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) installed

Clone and set up the project environment:

````bash
# clone the repository
git clone https://github.com/vodkar/shushpy.git
cd shushpy

# create a project environment and install dependencies + the project
uv sync
````

You can run the CLI via uv without manually activating the virtual environment:

````bash
# show CLI help
uv run shushpy --help

# strip a single file to stdout
uv run shushpy path/to/file.py

# strip a directory recursively in-place
uv run shushpy src/ --inplace

# read from stdin, write to stdout
cat script.py | uv run shushpy
````

Alternatively, if you prefer explicit installation into the environment:

````bash
uv pip install -e .
````

Then you can use the console script directly:

````bash
shushpy --help
````

## CLI

````text
usage: shushpy [-h] [--inplace] [--encoding ENCODING] [--recursive] [--no-recursive]
                   [--log-level {CRITICAL,ERROR,WARNING,INFO,DEBUG}]
                   [paths ...]

Remove all comments and docstrings from Python code.

positional arguments:
  paths                 Files or directories to process. If omitted, read from stdin and write to stdout.

options:
  -h, --help            show this help message and exit
  --inplace             Rewrite files in place. Required for multiple-file outputs.
  --encoding ENCODING   Text encoding for reading/writing files (default: utf-8).
  --recursive           Recurse into subdirectories (default: enabled).
  --no-recursive        Disable recursion when processing directories.
  --log-level           Set the logging level (default: WARNING).
````

Notes:
- When not using `--inplace`, the CLI writes to stdout. If your input expands to multiple files, the CLI refuses to stream multiple outputs to stdout—use `--inplace` in that case.
- When no paths are provided, the CLI reads from stdin and writes to stdout.

## Library usage

The library exposes a focused API in the `shushpy` package.

- `strip_comments(source: str) -> str`
- `strip_file(path: str | Path, *, inplace: bool = False, encoding: str = "utf-8") -> str`
- `strip_path(path: str | Path, *, inplace: bool = False, encoding: str = "utf-8", recursive: bool = True) -> dict[str, str]`
- `strip_paths(paths: list[str | Path], *, inplace: bool = False, encoding: str = "utf-8", recursive: bool = True) -> dict[str, str]`

Minimal examples:

````python
from __future__ import annotations

from pathlib import Path
from typing import Final

from shushpy import strip_comments, strip_file, strip_path, strip_paths

# Example 1: Process a source string
SOURCE: Final[str] = """
\"\"\"Module docstring\"\"\"

def add(a: int, b: int) -> int:
    \"\"\"Add two numbers\"\"\"
    return a + b  # inline comment
"""
cleaned: str = strip_comments(SOURCE)
print(cleaned)

# Example 2: Process a single file to a string (no in-place modification)
result_str: str = strip_file("path/to/file.py", inplace=False)

# Example 3: Process a directory recursively, in place
modified: dict[str, str] = strip_path("src", inplace=True, recursive=True)

# Example 4: Process multiple mixed paths, no in-place (returns mapping path->content)
collected: dict[str, str] = strip_paths([Path("a.py"), Path("pkg/")], inplace=False)
````

## Behavior and guarantees

- AST-based: The tool parses Python code into an AST, removes docstrings via AST transformation, and regenerates the code via `ast.unparse`. Inline/block comments aren’t part of the AST, so they never appear in the output.
- Formatting: The output is re-generated source. Expect normalized formatting and possibly different quoting styles or minor layout changes.
- Errors: Invalid Python raises `SyntaxError`. I/O and encoding issues are surfaced with clear errors.
- Scope: Docstrings are removed at module, class, and (async) function levels.

## Development

Common workflows with uv:

````bash
# create or update the environment and install the project
uv sync

# run the CLI
uv run shushpy --help

# run the module directly
uv run python -m shushpy.cli --help

# build distributions (wheel and sdist)
uv build
````

Project metadata:
- Build backend: Hatchling
- Console script: `shushpy` (entry point at `shushpy.cli:main`)

## Release & Publishing

Checklist before release:
- Ensure you have a PyPI account and access to the project name "shushpy" (or choose a unique name).
- Create a PyPI API token and add it as a GitHub Secret named PYPI_API_TOKEN in the repository settings.
- Bump the version in pyproject.toml under [project] version to the new semantic version (e.g., "0.1.1").
- Update README and (optionally) a CHANGELOG with notable changes.
- Run tests locally:
  - uv sync
  - uv run pytest -q
- Build locally to verify artifacts:
  - uv build
- Commit and tag the release:
  - git add .
  - git commit -m "Release vX.Y.Z"
  - git tag vX.Y.Z
  - git push && git push --tags

Publishing options:
- GitHub Actions (recommended):
  - On pushing a tag like vX.Y.Z (or publishing a GitHub Release), the workflow at .github/workflows/publish.yml will:
    - Install deps with uv, run tests, build distributions, and publish to PyPI using PYPI_API_TOKEN.
- Manual (optional):
  - Build: uv build
  - Upload with Twine (ephemeral via uvx):
    - uvx twine upload dist/*
  - To test on TestPyPI (optional):
    - uv build
    - uvx twine upload --repository-url https://test.pypi.org/legacy/ dist/*
    - Install to verify: uvx pip install -i https://test.pypi.org/simple shushpy==X.Y.Z

Post-release verification:
- Install from PyPI and check CLI:
  - uvx pip install shushpy
  - uvx shushpy --help

## Limitations

- This tool removes docstrings and comments only; it does not attempt to remove dead code or perform obfuscation.
- Because output is regenerated, stable formatting is not guaranteed across Python minor versions if `ast.unparse` behavior changes.
- Python 3.12+ is required (uses modern `ast` behavior and typing features).

## License

See the repository’s LICENSE file.
