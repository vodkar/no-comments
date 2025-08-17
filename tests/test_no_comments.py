from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from shushpy import strip_comments, strip_file, strip_path, strip_paths

EXIT_SUCCESS: Final[int] = 0
EXIT_FAILURE: Final[int] = 1
EXIT_USAGE: Final[int] = 2


def _write_text(path: Path, data: str, *, encoding: str = "utf-8") -> None:
    """Write text to a file using a context manager."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="\n") as f:
        f.write(data)


def _read_text(path: Path, *, encoding: str = "utf-8") -> str:
    """Read text from a file using a context manager."""
    with path.open("r", encoding=encoding) as f:
        return f.read()


def _has_leading_docstring_in_body(body: list[ast.stmt]) -> bool:
    """Return True if the body begins with a docstring expression."""
    if not body:
        return False
    first: ast.stmt = body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        return isinstance(first.value.value, str)
    return False


def _parse(source: str) -> ast.Module:
    """Parse source into an AST Module."""
    mod: ast.Module = ast.parse(source)
    return mod


def test_strip_comments_removes_module_class_function_docstrings_and_inline_comments() -> (
    None
):
    """Verify docstrings and inline comments are removed while code remains valid."""
    source: str = (
        '"""Module docstring."""\n'
        "# top-level comment\n"
        "class C:\n"
        '    """Class docstring."""\n'
        "    def f(self, x: int) -> int:\n"
        '        """Function docstring."""\n'
        "        y = x + 1  # inline\n"
        "        return y\n"
        "\n"
        "# trailing comment\n"
    )

    result: str = strip_comments(source)

    # Ensure trailing newline exists for POSIX-friendly formatting.
    assert result.endswith("\n")

    # Ensure there are no hash comments left for this particular input.
    assert "#" not in result

    # Parse and ensure no leading docstrings in module/class/function bodies.
    mod: ast.Module = _parse(result)
    assert not _has_leading_docstring_in_body(mod.body)

    # Find class C.
    cls_candidates: list[ast.ClassDef] = [
        n for n in mod.body if isinstance(n, ast.ClassDef)
    ]
    assert len(cls_candidates) == 1
    cls_c: ast.ClassDef = cls_candidates[0]
    assert cls_c.name == "C"
    assert not _has_leading_docstring_in_body(cls_c.body)

    # Find function f inside class C.
    func_candidates: list[ast.FunctionDef] = [
        n for n in cls_c.body if isinstance(n, ast.FunctionDef)
    ]
    assert len(func_candidates) == 1
    fn_f: ast.FunctionDef = func_candidates[0]
    assert fn_f.name == "f"
    assert not _has_leading_docstring_in_body(fn_f.body)


def test_strip_comments_preserves_string_literals_that_look_like_comments() -> None:
    """Ensure string literals containing '#' are preserved as-is."""
    source: str = 'def message() -> str:\n    return "# not a comment, inside string"\n'
    result: str = strip_comments(source)
    assert (
        '"# not a comment, inside string"' in result
        or "'# not a comment, inside string'" in result
    )
    # Code remains valid
    _ = _parse(result)


def test_strip_file_inplace_and_no_inplace(tmp_path: Path) -> None:
    """Verify strip_file returns transformed content and optionally writes in-place."""
    original: str = (
        '"""Docstring."""\n'
        "def add(a: int, b: int) -> int:\n"
        "    return a + b  # inline comment\n"
    )
    p: Path = tmp_path / "sample.py"
    _write_text(p, original)

    # No in-place: return transformed, file unchanged.
    transformed: str = strip_file(p, inplace=False)
    assert '"""' not in transformed
    assert "#" not in transformed
    on_disk_before: str = _read_text(p)
    assert on_disk_before == original

    # In-place: file contents updated.
    transformed2: str = strip_file(p, inplace=True)
    assert transformed2 == transformed
    on_disk_after: str = _read_text(p)
    assert on_disk_after == transformed


def test_strip_file_rejects_non_python_suffix(tmp_path: Path) -> None:
    """strip_file should reject non-.py files."""
    p: Path = tmp_path / "not_python.txt"
    _write_text(p, "print('hello')  # comment\n")
    with pytest.raises(ValueError):
        _ = strip_file(p)


def test_strip_path_directory_inplace_and_no_inplace(tmp_path: Path) -> None:
    """Verify strip_path processes directories and optionally writes in-place."""
    src_dir: Path = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    p1: Path = src_dir / "a.py"
    p2: Path = src_dir / "b.py"
    _write_text(
        p1,
        '"""A doc"""\n# c1\nx: int = 1  # inline\n',
    )
    _write_text(
        p2,
        '"""B doc"""\n# c2\n\ny: int = 2  # inline\n',
    )

    # No in-place: returns map, files unchanged.
    results_no_inplace: dict[str, str] = strip_path(
        src_dir, inplace=False, recursive=True
    )
    assert str(p1) in results_no_inplace and str(p2) in results_no_inplace
    assert "#" not in results_no_inplace[str(p1)]
    assert "#" not in results_no_inplace[str(p2)]
    assert '"""' not in results_no_inplace[str(p1)]
    assert '"""' not in results_no_inplace[str(p2)]
    assert _read_text(p1).startswith('"""')  # still original
    assert _read_text(p2).startswith('"""')  # still original

    # In-place: files updated on disk.
    results_inplace: dict[str, str] = strip_path(src_dir, inplace=True, recursive=True)
    assert results_inplace[str(p1)] == _read_text(p1)
    assert results_inplace[str(p2)] == _read_text(p2)
    assert '"""' not in _read_text(p1)
    assert '"""' not in _read_text(p2)
    assert "#" not in _read_text(p1)
    assert "#" not in _read_text(p2)


def test_strip_paths_mixed_inputs(tmp_path: Path) -> None:
    """Verify strip_paths handles a mix of file and directory inputs."""
    d: Path = tmp_path / "pkg"
    d.mkdir(parents=True, exist_ok=True)
    p_dir_file: Path = d / "c.py"
    p_single: Path = tmp_path / "single.py"
    _write_text(p_dir_file, '"""Doc"""\n# comment\nz: int = 3  # inline\n')
    _write_text(p_single, '"""Doc"""\n# comment\nw: int = 4  # inline\n')

    results: dict[str, str] = strip_paths([d, p_single], inplace=False, recursive=True)
    assert str(p_dir_file) in results
    assert str(p_single) in results
    assert "#" not in results[str(p_dir_file)]
    assert "#" not in results[str(p_single)]
    assert '"""' not in results[str(p_dir_file)]
    assert '"""' not in results[str(p_single)]


def test_cli_stdin_to_stdout_roundtrip() -> None:
    """CLI should read from stdin and write stripped result to stdout."""
    source: str = '"""Doc"""\ndef f() -> int:\n    # inline comment\n    return 42\n'
    expected: str = strip_comments(source)
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "shushpy.cli"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == EXIT_SUCCESS
    assert proc.stdout == expected
    assert proc.stderr == ""


def test_cli_single_file_to_stdout(tmp_path: Path) -> None:
    """CLI should write a single-file output to stdout when not using --inplace."""
    src: str = '"""Doc"""\nvalue: int = 5  # comment\n'
    p: Path = tmp_path / "one.py"
    _write_text(p, src)
    expected: str = strip_comments(src)

    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "shushpy.cli", str(p)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == EXIT_SUCCESS
    assert proc.stdout == expected
    assert proc.stderr == ""


def test_cli_directory_inplace(tmp_path: Path) -> None:
    """CLI should modify files in place when --inplace is provided for a directory."""
    d: Path = tmp_path / "pkg"
    d.mkdir(parents=True, exist_ok=True)
    p1: Path = d / "a.py"
    p2: Path = d / "b.py"
    src1: str = '"""Doc A"""\n# c\nA: int = 1  # inline\n'
    src2: str = '"""Doc B"""\n# c\nB: int = 2  # inline\n'
    _write_text(p1, src1)
    _write_text(p2, src2)
    expected1: str = strip_comments(src1)
    expected2: str = strip_comments(src2)

    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "shushpy.cli", str(d), "--inplace"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == EXIT_SUCCESS
    assert proc.stdout == ""
    assert (p1.read_text() == expected1) and (p2.read_text() == expected2)


def test_cli_refuses_multiple_outputs_to_stdout(tmp_path: Path) -> None:
    """CLI should refuse to write multiple outputs to stdout without --inplace."""
    d: Path = tmp_path / "pkg"
    d.mkdir(parents=True, exist_ok=True)
    _write_text(d / "a.py", "x: int = 1  # c\n")
    _write_text(d / "b.py", "y: int = 2  # c\n")

    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "shushpy.cli", str(d)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == EXIT_USAGE
    assert proc.stdout == ""


def test_cli_nonexistent_path_returns_failure(tmp_path: Path) -> None:
    """CLI should return failure for non-existent input paths."""
    bogus: Path = tmp_path / "does_not_exist.py"
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "shushpy.cli", str(bogus)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == EXIT_FAILURE


def test_cli_invalid_syntax_returns_failure(tmp_path: Path) -> None:
    """CLI should return failure for files with invalid syntax."""
    bad: Path = tmp_path / "bad.py"
    _write_text(bad, "def f(:\n    pass\n")
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "shushpy.cli", str(bad)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == EXIT_FAILURE
