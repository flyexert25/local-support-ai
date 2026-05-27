from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".csv",
    ".tsv",
    ".qml",
    ".qss",
    ".ui",
    ".xml",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".svg",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "build",
    "dist",
    "site-packages",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def staged_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = repo_root / line.strip()
        if path.is_file():
            paths.append(path)
    return paths


def likely_text_file(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    return path.suffix.lower() in TEXT_EXTENSIONS


def read_utf8(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def mojibake_fragments() -> set[str]:
    # Russian Unicode ranges, generated without embedding Cyrillic literals.
    alphabet = "".join(chr(code) for code in range(0x0410, 0x0450)) + chr(0x0401) + chr(0x0451)
    fragments: set[str] = {"\u0432\u0402", "\u00e2\u20ac"}
    for char in alphabet:
        try:
            fragment = char.encode("utf-8").decode("cp1251")
        except UnicodeError:
            continue
        if fragment != char:
            fragments.add(fragment)
    return fragments


MOJIBAKE_FRAGMENTS = mojibake_fragments()


def mojibake_score(text: str) -> int:
    return sum(text.count(fragment) for fragment in MOJIBAKE_FRAGMENTS)


def looks_like_mojibake(text: str) -> bool:
    return mojibake_score(text) >= 3 or "\ufffd" in text


def try_repair_mojibake(text: str) -> str | None:
    # Typical case: UTF-8 bytes were decoded as cp1251 and saved again.
    if not looks_like_mojibake(text):
        return None

    markers_before = mojibake_score(text)
    try:
        repaired = text.encode("cp1251").decode("utf-8")
    except UnicodeError:
        repaired_lines: list[str] = []
        changed = False
        for line in text.splitlines(keepends=True):
            if looks_like_mojibake(line):
                try:
                    repaired_line = line.encode("cp1251").decode("utf-8")
                except UnicodeError:
                    repaired_line = line
                if mojibake_score(repaired_line) < mojibake_score(line):
                    line = repaired_line
                    changed = True
            repaired_lines.append(line)
        return "".join(repaired_lines) if changed else None

    if mojibake_score(repaired) >= markers_before:
        return None
    return repaired


def normalize_text(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip(" \t") for line in lines]
    return "\n".join(lines).rstrip("\n") + "\n"


def fix_file(path: Path) -> tuple[bool, str]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
        source = "utf8"
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp1251")
            source = "cp1251"
        except UnicodeDecodeError:
            return False, "binary/unknown encoding"

    repaired = try_repair_mojibake(text)
    if repaired is not None:
        text = repaired
        source += "+mojibake_fix"

    normalized = normalize_text(text)
    encoded = normalized.encode("utf-8")
    changed = encoded != raw
    if changed:
        path.write_bytes(encoded)
    return changed, source


def main() -> int:
    parser = argparse.ArgumentParser(description="UTF-8 and mojibake guard for repository files.")
    parser.add_argument("--staged", action="store_true", help="Process only staged files.")
    parser.add_argument("--fix", action="store_true", help="Apply fixes in place.")
    args = parser.parse_args()

    repo_root = get_repo_root()
    files = staged_files(repo_root) if args.staged else [p for p in repo_root.rglob("*") if p.is_file()]
    files = [p for p in files if likely_text_file(p)]

    bad_files: list[Path] = []
    fixed_files: list[Path] = []

    for path in files:
        text = read_utf8(path)
        has_mojibake = text is not None and looks_like_mojibake(text)
        if text is None or has_mojibake:
            bad_files.append(path)
            if args.fix:
                changed, _ = fix_file(path)
                if changed:
                    fixed_files.append(path)

    if args.fix and fixed_files:
        rels = [str(p.relative_to(repo_root)) for p in fixed_files]
        subprocess.run(["git", "-C", str(repo_root), "add", *rels], check=False)
        print("Encoding guard: fixed files:")
        for rel in rels:
            print(f"  - {rel}")

    remaining_bad: list[str] = []
    for path in bad_files:
        text = read_utf8(path)
        if text is None or looks_like_mojibake(text):
            remaining_bad.append(str(path.relative_to(repo_root)))

    if remaining_bad:
        print("Encoding guard: found files with non-UTF8 or possible mojibake:")
        for rel in remaining_bad:
            print(f"  - {rel}")
        print("Run: python scripts/encoding_guard.py --staged --fix")
        return 1

    print("Encoding guard: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
