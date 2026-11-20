import json
import sys
from pathlib import Path

MODULES = {
    "pipeline": (("/features/pipeline/",), 90.0),
    "door": (("/features/door/",), 80.0),
    "monitor": (("/features/monitor/",), 85.0),
    "application": (("/features/", "/application/"), 90.0),
    "global": ((), 80.0),
}


def percentage(files, needles):
    selected = {
        path: data for path, data in files.items() if all(needle in path.replace("\\", "/") for needle in needles)
    }
    if not selected:
        return None
    total = sum(data["summary"]["num_statements"] + data["summary"]["num_branches"] for data in selected.values())
    if total == 0:
        return 100.0
    covered = sum(data["summary"]["covered_lines"] + data["summary"]["covered_branches"] for data in selected.values())
    return 100.0 * covered / total


def main():
    report_path = Path(sys.argv[1] if len(sys.argv) > 1 else "coverage.json")
    files = json.loads(report_path.read_text(encoding="utf-8"))["files"]
    failures = []
    for name, (needles, threshold) in MODULES.items():
        value = percentage(files, needles)
        if value is None:
            failures.append(f"{name}: no se encontraron archivos para {needles}")
            continue
        status = "OK" if value >= threshold else "FAIL"
        print(f"{name}: {value:.1f}% (umbral {threshold:.1f}%) {status}")
        if value < threshold:
            failures.append(f"{name}: {value:.1f}% < {threshold:.1f}%")
    if failures:
        print("Cobertura insuficiente:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
