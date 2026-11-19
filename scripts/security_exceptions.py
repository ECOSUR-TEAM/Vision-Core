import argparse
import json
import re
from pathlib import Path

_ID_PATTERN = re.compile(r"^(?:GHSA-[a-z0-9-]+|CVE-\d{4}-\d+)$", re.IGNORECASE)
_REQUIRED_FIELDS = {"id", "component", "version", "reason", "registered", "review_by", "owner"}


def load_exceptions(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("security-exceptions: version debe ser 1")
    exceptions = data.get("exceptions")
    if not isinstance(exceptions, list):
        raise ValueError("security-exceptions: exceptions debe ser una lista")
    for item in exceptions:
        if not isinstance(item, dict):
            raise ValueError("security-exceptions: cada excepcion debe ser un objeto")
        missing = _REQUIRED_FIELDS - item.keys()
        if missing:
            raise ValueError(f"security-exceptions: campos faltantes en {item.get('id')}: {sorted(missing)}")
        if not _ID_PATTERN.match(item["id"]):
            raise ValueError(f"security-exceptions: identificador invalido: {item['id']}")
        for flag in ("trivy", "dependency_review"):
            if flag in item and not isinstance(item[flag], bool):
                raise ValueError(f"security-exceptions: {flag} debe ser booleano en {item['id']}")
    return exceptions


def build_lists(exceptions):
    trivy_ids = [item["id"] for item in exceptions if item.get("trivy", True)]
    ghsas = [
        item["id"]
        for item in exceptions
        if item.get("dependency_review", True) and item["id"].upper().startswith("GHSA-")
    ]
    return trivy_ids, ghsas


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate vulnerability scanner exception lists")
    parser.add_argument("--exceptions", default=".github/security-exceptions.yml")
    parser.add_argument("--trivy-ignore")
    parser.add_argument("--github-output")
    args = parser.parse_args(argv)

    trivy_ids, ghsas = build_lists(load_exceptions(args.exceptions))
    if args.trivy_ignore:
        Path(args.trivy_ignore).write_text("".join(f"{item}\n" for item in trivy_ids), encoding="utf-8")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(f"allow-ghsas={','.join(ghsas)}\n")
    print(json.dumps({"trivy_ignores": trivy_ids, "allow_ghsas": ghsas}))


if __name__ == "__main__":
    main()
