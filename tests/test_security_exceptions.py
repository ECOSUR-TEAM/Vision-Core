import json

import pytest

from scripts.security_exceptions import build_lists, load_exceptions, main


def _exception(identifier, trivy=True, dependency_review=True):
    return {
        "id": identifier,
        "component": "demo",
        "version": "1.0.0",
        "reason": "sin correccion",
        "registered": "2026-01-01",
        "review_by": "2026-02-01",
        "owner": "seguridad",
        "trivy": trivy,
        "dependency_review": dependency_review,
    }


def test_build_lists_filters_by_scanner():
    exceptions = [
        _exception("CVE-2026-0001"),
        _exception("GHSA-aaaa-bbbb-cccc", trivy=False),
        _exception("GHSA-dddd-eeee-ffff", dependency_review=False),
    ]
    trivy_ids, ghsas = build_lists(exceptions)
    assert trivy_ids == ["CVE-2026-0001", "GHSA-dddd-eeee-ffff"]
    assert ghsas == ["GHSA-aaaa-bbbb-cccc"]


def test_load_exceptions_rejects_invalid_id(tmp_path):
    path = tmp_path / "exceptions.yml"
    path.write_text(json.dumps({"version": 1, "exceptions": [_exception("not-an-id")]}))
    with pytest.raises(ValueError, match="identificador invalido"):
        load_exceptions(path)


def test_main_writes_scanner_inputs(tmp_path):
    path = tmp_path / "exceptions.yml"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "exceptions": [_exception("CVE-2026-0001"), _exception("GHSA-aaaa-bbbb-cccc")],
            }
        )
    )
    ignore = tmp_path / ".trivyignore"
    output = tmp_path / "github_output"
    main(["--exceptions", str(path), "--trivy-ignore", str(ignore), "--github-output", str(output)])

    assert ignore.read_text().splitlines() == ["CVE-2026-0001", "GHSA-aaaa-bbbb-cccc"]
    assert "allow-ghsas=GHSA-aaaa-bbbb-cccc" in output.read_text()
