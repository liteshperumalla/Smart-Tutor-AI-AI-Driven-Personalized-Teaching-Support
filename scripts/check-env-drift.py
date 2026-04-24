#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys


def load_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    targets = [
        {
            "source": repo_root / ".env.example",
            "target": repo_root / ".env.production",
            "ignore_prefixes": tuple(),
            "ignore_keys": {"JWT_SECRET_KEY"},
        },
        {
            "source": repo_root / ".env.example",
            "target": repo_root / ".env.prod",
            "ignore_prefixes": ("VERCEL_", "TURBO_", "NX_", "NEXT_PUBLIC_", "BACKEND_"),
            "ignore_keys": {"VERCEL"},
        },
        {
            "source": repo_root / "frontend" / ".env.local.example",
            "target": repo_root / "frontend" / ".env.local",
            "ignore_prefixes": ("VERCEL_", "TURBO_", "NX_"),
            "ignore_keys": {"VERCEL", "BACKEND_API_BASE_URL", "NEXT_PUBLIC_BACKEND_URL"},
            "optional": True,
        },
    ]

    failures: list[str] = []
    for item in targets:
        source = item["source"]
        target = item["target"]
        optional = item.get("optional", False)
        if not source.exists():
            if optional:
                print(
                    f"Skipping optional contract pair: {source.relative_to(repo_root)} "
                    f"-> {target.relative_to(repo_root)}"
                )
                continue
            failures.append(f"missing source contract file: {source}")
            continue

        if not target.exists():
            print(
                f"Skipping optional target file: {target.relative_to(repo_root)} "
                f"(source contract: {source.relative_to(repo_root)})"
            )
            continue

        source_keys = load_keys(source)
        target_keys = load_keys(target)

        undocumented = sorted(
            key
            for key in (target_keys - source_keys)
            if key not in item["ignore_keys"]
            and not any(key.startswith(prefix) for prefix in item["ignore_prefixes"])
        )
        if undocumented:
            failures.append(
                f"{target.relative_to(repo_root)} contains undocumented keys not declared in {source.relative_to(repo_root)}: {', '.join(undocumented)}"
            )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print("Environment contract check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
