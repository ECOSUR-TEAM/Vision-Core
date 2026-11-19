from scripts.extract_changelog import extract_changelog_section


def test_extract_changelog_section():
    changelog = """# Changelog

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
    section = extract_changelog_section(changelog, "0.1.0")
    assert "### Added" in section
    assert "Initial release" in section
    assert "Next feature" not in section


def test_extract_changelog_missing_section():
    import pytest

    with pytest.raises(SystemExit, match=r"CHANGELOG\.md"):
        extract_changelog_section("# Changelog\n", "9.9.9")
