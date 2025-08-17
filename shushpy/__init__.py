# shushpy/shushpy/__init__.py
"""
Utilities to strip all comments and docstrings from Python source code.

This module exposes a small, focused API for removing:
- Inline comments (e.g., `# comment`)
- Block comments
- Docstrings at module, class, and (async) function scope

Implementation details:
- Docstrings are removed by transforming the AST and deleting leading string-literal
  expression statements from module/class/function bodies.
- All comments (including inline and block comments) are removed via `ast.unparse`,
  which regenerates code solely from the abstract syntax tree and drops comments.
- Formatting, quotes, and minor layout details may change because the code is unparsed
  from the AST. Semantics are preserved while comments and docstrings are removed.

This library has no third-party dependencies and integrates cleanly with uv or any
PEP 517/518-compliant package manager.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Final

__all__: Final[list[str]] = [
    "strip_comments",
    "strip_file",
    "strip_path",
    "strip_paths",
]

logger: logging.Logger = logging.getLogger(__name__)
PYTHON_SUFFIX: Final[str] = ".py"


class DocstringStripper(ast.NodeTransformer):
    """AST transformer that removes docstrings from modules, classes, and functions.

    Docstrings are represented as a leading `ast.Expr` node whose value is a simple
    string literal (i.e., `ast.Constant` with `str` value) for each body.

    Methods:
        visit_Module: Remove module-level docstring if present.
        visit_ClassDef: Remove class-level docstring if present, then visit children.
        visit_FunctionDef: Remove function-level docstring if present, then visit children.
        visit_AsyncFunctionDef: Remove async function-level docstring if present, then visit children.
    """

    @staticmethod
    def _strip_docstring_from_body(body: list[ast.stmt]) -> list[ast.stmt]:
        """Return a new body with a leading docstring removed, if present.

        Args:
            body: The list of statements for a node's body.

        Returns:
            A list of statements without a leading docstring expression.
        """
        if not body:
            return body

        first: ast.stmt = body[0]
        if isinstance(first, ast.Expr):
            value: ast.expr = first.value
            # In Python 3.12+, docstrings are represented as Constant(str).
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return body[1:]

        return body

    def visit_Module(self, node: ast.Module) -> ast.AST:  # noqa: N802 (AST API)
        node.body = self._strip_docstring_from_body(node.body)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:  # noqa: N802 (AST API)
        node.body = self._strip_docstring_from_body(node.body)
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802 (AST API)
        node.body = self._strip_docstring_from_body(node.body)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:  # noqa: N802 (AST API)
        node.body = self._strip_docstring_from_body(node.body)
        self.generic_visit(node)
        return node


def strip_comments(source: str) -> str:
    """Strip all comments and docstrings from a Python source string.

    This function:
    - Removes module/class/function docstrings
    - Eliminates all comments (inline and block) by unparsing from the AST

    Args:
        source: Python source code to transform.

    Returns:
        The transformed source code with comments and docstrings removed.

    Raises:
        SyntaxError: If the input source is not syntactically valid Python.
        ValueError: If `source` is empty or whitespace only.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a str")

    if source.strip() == "":
        raise ValueError("source must not be empty or whitespace only")

    # Parse, strip docstrings, and unparse to drop all comments.
    tree: ast.AST = ast.parse(source)
    stripper: DocstringStripper = DocstringStripper()
    new_tree: ast.AST = stripper.visit(tree)
    ast.fix_missing_locations(new_tree)

    transformed: str = ast.unparse(new_tree)
    # Ensure a trailing newline for POSIX-friendly formatting.
    if not transformed.endswith("\n"):
        transformed = f"{transformed}\n"
    return transformed


def _read_text(path: Path, encoding: str) -> str:
    """Read file content using the provided encoding.

    Args:
        path: Path to the file.
        encoding: Text encoding.

    Returns:
        File content as a string.

    Raises:
        FileNotFoundError: If the file is not found.
        UnicodeDecodeError: If decoding fails.
    """
    with path.open("r", encoding=encoding, newline="") as f:
        data: str = f.read()
    return data


def _write_text(path: Path, data: str, encoding: str) -> None:
    """Write text to a file using the provided encoding.

    Args:
        path: Path to the file.
        data: Text content to write.
        encoding: Text encoding.

    Raises:
        UnicodeEncodeError: If encoding fails.
        OSError: For filesystem-related errors during write.
    """
    # Create parent directory if missing to fail fast with clear intent.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="\n") as f:
        f.write(data)


def strip_file(
    path: str | Path,
    *,
    inplace: bool = False,
    encoding: str = "utf-8",
) -> str:
    """Strip comments and docstrings from a single Python file.

    Args:
        path: Path to a `.py` file.
        inplace: If True, overwrite the file with the stripped content.
        encoding: File encoding used for reading and (optionally) writing.

    Returns:
        The stripped source code.

    Raises:
        ValueError: If `path` does not point to a `.py` file.
        FileNotFoundError: If `path` does not exist.
        SyntaxError: If the file contains invalid Python code.
        UnicodeError: If decoding or encoding fails.
        OSError: For filesystem-related errors when writing inplace.
    """
    p: Path = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No such file: {p}")
    if not p.is_file():
        raise ValueError(f"Expected a file path, got directory or non-file: {p}")
    if p.suffix.lower() != PYTHON_SUFFIX:
        raise ValueError(f"Expected a Python file with '.py' suffix, got: {p.name}")

    original: str = _read_text(p, encoding=encoding)
    stripped: str = strip_comments(original)
    if inplace:
        _write_text(p, stripped, encoding=encoding)
    return stripped


def _iter_python_files(root: Path, recursive: bool) -> list[Path]:
    """Collect Python files under a path.

    Args:
        root: Root path (file or directory).
        recursive: If True and root is a directory, recurse into subdirectories.

    Returns:
        A list of Python file paths to process.

    Raises:
        ValueError: If `root` is neither a file nor a directory.
    """
    if root.is_file():
        return [root] if root.suffix.lower() == PYTHON_SUFFIX else []

    if root.is_dir():
        if not recursive:
            return [
                p
                for p in root.iterdir()
                if p.is_file() and p.suffix.lower() == PYTHON_SUFFIX
            ]
        return [p for p in root.rglob(f"*{PYTHON_SUFFIX}") if p.is_file()]

    raise ValueError(f"Path is neither a file nor a directory: {root}")


def strip_path(
    path: str | Path,
    *,
    inplace: bool = False,
    encoding: str = "utf-8",
    recursive: bool = True,
) -> dict[str, str]:
    """Strip comments and docstrings from a path (file or directory).

    If `path` is a file, it must have a `.py` suffix. If `path` is a directory,
    all `.py` files beneath it will be processed.

    Args:
        path: File or directory path.
        inplace: If True, overwrite the processed files with stripped content.
        encoding: File encoding used for reading and (optionally) writing.
        recursive: If True and `path` is a directory, process files recursively.

    Returns:
        A mapping from file path (string) to the stripped source content.

    Raises:
        FileNotFoundError: If `path` does not exist.
        SyntaxError: If any processed file contains invalid Python code.
        UnicodeError: If decoding or encoding fails for any file.
        OSError: For filesystem-related errors when writing inplace.
        ValueError: If `path` is neither a file nor a directory, or if a single file
            without `.py` suffix is provided.
    """
    root: Path = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"No such path: {root}")

    files: list[Path] = _iter_python_files(root, recursive=recursive)
    if root.is_file() and not files:
        raise ValueError(f"Expected a Python file with '.py' suffix, got: {root.name}")

    results: dict[str, str] = {}
    for file_path in files:
        try:
            transformed: str = strip_file(file_path, inplace=inplace, encoding=encoding)
            results[str(file_path)] = transformed
        except SyntaxError:
            # Re-raise SyntaxError as-is for transparency.
            logger.exception("SyntaxError while stripping %s", file_path)
            raise
        except (UnicodeError, OSError) as exc:
            logger.exception("I/O or encoding error while stripping %s", file_path)
            raise exc

    return results


def strip_paths(
    paths: list[str | Path],
    *,
    inplace: bool = False,
    encoding: str = "utf-8",
    recursive: bool = True,
) -> dict[str, str]:
    """Strip comments and docstrings from multiple paths (files and/or directories).

    Args:
        paths: A list of file or directory paths.
        inplace: If True, overwrite the processed files with stripped content.
        encoding: File encoding used for reading and (optionally) writing.
        recursive: If True, recurse into subdirectories for any directory paths.

    Returns:
        A mapping from file path (string) to the stripped source content across all inputs.

    Raises:
        FileNotFoundError: If any path does not exist.
        SyntaxError: If any processed file contains invalid Python code.
        UnicodeError: If decoding or encoding fails for any file.
        OSError: For filesystem-related errors when writing inplace.
        ValueError: If any provided path is neither a file nor a directory.
    """
    aggregated: dict[str, str] = {}
    for p in paths:
        result_for_path: dict[str, str] = strip_path(
            p, inplace=inplace, encoding=encoding, recursive=recursive
        )
        aggregated.update(result_for_path)
    return aggregated
