import sys
from pathlib import Path

import pytest

from scripts.extract_changelog import extract_changelog_section, main

STABLE_CHANGELOG = """# Changelog

## [Unreleased]

### Added
- Next feature

## [0.1.0] - 2026-11-19

### Added
- Initial release

## [0.0.9]

### Fixed
- Older fix
"""

PRERELEASE_CHANGELOG = """# Changelog

## [0.1.0-rc.1] - 2026-11-20

### Fixed
- Release candidate notes

## [0.1.0] - 2026-11-19

### Added
- Initial release
"""


def test_extract_changelog_section():
    section = extract_changelog_section(STABLE_CHANGELOG, "0.1.0")
    assert "### Added" in section
    assert "Initial release" in section
    assert "Next feature" not in section


def test_extract_changelog_missing_section():
    with pytest.raises(SystemExit, match=r"CHANGELOG\.md"):
        extract_changelog_section("# Changelog\n", "9.9.9")


def test_main_extracts_prerelease_section(tmp_path, monkeypatch, capsys):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(PRERELEASE_CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["extract_changelog.py", "0.1.0-rc.1", str(changelog)])

    main()

    output = capsys.readouterr().out
    assert "Release candidate notes" in output
    assert "Initial release" not in output


def test_main_does_not_fall_back_from_prerelease_to_stable(tmp_path, monkeypatch):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(STABLE_CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["extract_changelog.py", "0.1.0-rc.1", str(changelog)])

    with pytest.raises(SystemExit, match=r"0\.1\.0-rc\.1"):
        main()


def test_main_reports_usage(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["extract_changelog.py"])

    with pytest.raises(SystemExit, match="usage"):
        main()


def test_project_version_is_exposed():
    import tomllib

    from vision_core import __version__

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as source:
        expected = tomllib.load(source)["project"]["version"]

    assert __version__ == expected
