"""Extract one Keep a Changelog release section for GitHub release notes."""

import re
import sys
from pathlib import Path


def extract_changelog_section(changelog: str, version: str) -> str:
    match = re.search(
        rf"^## \[{re.escape(version)}(?:\][^\n]*)?$",
        changelog,
        flags=re.MULTILINE,
    )
    if match is None:
        raise SystemExit(f"CHANGELOG.md does not contain section [{version}]")

    start = match.end()
    following = re.search(r"^## \[", changelog[start:], flags=re.MULTILINE)
    end = start + following.start() if following else len(changelog)
    return changelog[start:end].strip()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: extract_changelog.py VERSION CHANGELOG")
    version = sys.argv[1].split("-", 1)[0]
    changelog = Path(sys.argv[2]).read_text(encoding="utf-8")
    print(extract_changelog_section(changelog, version))


if __name__ == "__main__":
    main()
