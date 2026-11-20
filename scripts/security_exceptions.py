import argparse
import json
import re
from datetime import date
from pathlib import Path

_ID_PATTERN = re.compile(r"^(?:GHSA-[a-z0-9-]+|CVE-\d{4}-\d+)$", re.IGNORECASE)
_REQUIRED_FIELDS = {"id", "component", "version", "reason", "registered", "review_by", "owner"}
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / ".github" / "security-exceptions.schema.json"


def _validate_schema(data, schema, location="$"):
    if "const" in schema:
        expected_value = schema["const"]
        if (
            isinstance(data, bool) != isinstance(expected_value, bool)
            or not isinstance(data, type(expected_value))
            or data != expected_value
        ):
            raise ValueError(f"security-exceptions: {location} debe ser {expected_value!r}")

    expected = schema.get("type")
    if expected == "object":
        if not isinstance(data, dict):
            raise ValueError(f"security-exceptions: {location} debe ser un objeto")
        properties = schema.get("properties", {})
        for field in schema.get("required", []):
            if field not in data:
                raise ValueError(f"security-exceptions: falta {location}.{field}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(data) - set(properties))
            if extra:
                raise ValueError(f"security-exceptions: propiedades no permitidas en {location}: {extra}")
        for field, value in data.items():
            if field in properties:
                _validate_schema(value, properties[field], f"{location}.{field}")
    elif expected == "array":
        if not isinstance(data, list):
            raise ValueError(f"security-exceptions: {location} debe ser una lista")
        for index, item in enumerate(data):
            _validate_schema(item, schema.get("items", {}), f"{location}[{index}]")
    elif expected == "string":
        if not isinstance(data, str):
            raise ValueError(f"security-exceptions: {location} debe ser una cadena")
        if len(data) < schema.get("minLength", 0):
            raise ValueError(f"security-exceptions: {location} no puede estar vacio")
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, data):
            raise ValueError(f"security-exceptions: valor invalido en {location}: {data}")
    elif expected == "boolean" and not isinstance(data, bool):
        raise ValueError(f"security-exceptions: {location} debe ser booleano")


def load_exceptions(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("security-exceptions: la raiz debe ser un objeto")
    version = data.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
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
        for field in ("registered", "review_by"):
            try:
                parsed = date.fromisoformat(item[field])
            except (TypeError, ValueError) as error:
                raise ValueError(f"security-exceptions: {field} invalido en {item['id']}: {error}") from error
            if field == "review_by" and parsed < date.today():
                raise ValueError(f"security-exceptions: review_by vencido en {item['id']}: {item[field]}")
        for flag in ("trivy", "dependency_review"):
            if flag in item and not isinstance(item[flag], bool):
                raise ValueError(f"security-exceptions: {flag} debe ser booleano en {item['id']}")
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    _validate_schema(data, schema)
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
