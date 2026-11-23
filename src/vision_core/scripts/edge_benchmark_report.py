import csv
import json
from pathlib import Path
from typing import Any


def flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {
        key: value for key, value in row.items() if isinstance(value, (str, int, float)) and not isinstance(value, bool)
    }
    flat["detection_model_id"] = row["detection"]["model_id"]
    flat["detection_precision"] = row["detection"]["precision"]
    flat["embedding_model_id"] = row["embedding"]["model_id"]
    flat["embedding_precision"] = row["embedding"]["precision"]
    metrics = row.get("metrics") or {}
    flat["detection_p50_ms"] = metrics.get("detection", {}).get("p50_ms")
    flat["detection_p95_ms"] = metrics.get("detection", {}).get("p95_ms")
    flat["embedding_p50_ms"] = metrics.get("embedding", {}).get("p50_ms")
    flat["embedding_p95_ms"] = metrics.get("embedding", {}).get("p95_ms")
    flat["frame_p95_ms"] = metrics.get("frame", {}).get("p95_ms")
    flat["fps_end_to_end"] = metrics.get("fps_end_to_end")
    flat["memory_peak_tracemalloc_mb"] = metrics.get("memory_peak_tracemalloc_mb")
    flat["energy_j"] = metrics.get("energy_j")
    quality = row.get("quality") or {}
    flat["quality_passed"] = quality.get("passed")
    flat["quality_detection_map50"] = quality.get("checks", {}).get("detection_map50", {}).get("value")
    flat["quality_identity_recall"] = quality.get("checks", {}).get("identity_recall_at_1", {}).get("value")
    flat["identity_source"] = row.get("quality_metrics", {}).get("identity", {}).get("source")
    flat["budget_passed"] = row.get("budget", {}).get("passed")
    flat["recommended"] = row.get("recommended")
    return flat


def render_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Matriz comparativa edge / INT8",
        "",
        f"- Generado: `{matrix['generated_at']}`",
        f"- Config: `{matrix['config']['path']}` (`{matrix['config']['sha256'][:12]}`)",
        f"- Semilla del conjunto de validación: `{matrix['validation_set']['seed']}`",
        f"- Calidad se evalúa antes que FPS; umbrales: `{matrix['quality_gates']}`",
        "",
        "| Perfil | Target | Precisión det/emb | Estado | Det p50/p95 (ms) | "
        "Emb p50/p95 (ms) | FPS | Memoria pico (MB) | map50 proxy | "
        "Recall ID | Calidad | Presupuesto | Recomendado |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for row in matrix["results"]:
        metrics = row.get("metrics") or {}
        detection = metrics.get("detection", {})
        embedding = metrics.get("embedding", {})
        quality = row.get("quality") or {}
        quality_det = quality.get("checks", {}).get("detection_map50", {}).get("value")
        quality_id = quality.get("checks", {}).get("identity_recall_at_1", {}).get("value")
        lines.append(
            (
                "| {profile} | {target} | {prec_det}/{prec_emb} | {status} | "
                "{det_p50}/{det_p95} | {emb_p50}/{emb_p95} | {fps} | {memory} | "
                "{map50} | {recall} | {quality} | {budget} | {recommended} |"
            ).format(
                profile=row["id"],
                target=row["target"],
                prec_det=row["detection"]["precision"],
                prec_emb=row["embedding"]["precision"],
                status=row["status"],
                det_p50=_format(detection.get("p50_ms")),
                det_p95=_format(detection.get("p95_ms")),
                emb_p50=_format(embedding.get("p50_ms")),
                emb_p95=_format(embedding.get("p95_ms")),
                fps=_format(metrics.get("fps_end_to_end")),
                memory=_format(metrics.get("memory_peak_tracemalloc_mb")),
                map50=_format(quality_det),
                recall=_format(quality_id),
                quality=_bool_label(quality.get("passed")),
                budget=_bool_label(row.get("budget", {}).get("passed")),
                recommended=_bool_label(row.get("recommended")),
            )
        )
    lines.extend(["", "## No medidos", ""])
    unreported = [row for row in matrix["results"] if row["status"] != "measured"]
    if unreported:
        for row in unreported:
            lines.append(f"- `{row['id']}`: {row.get('reason') or 'sin razón registrada'}")
    else:
        lines.append("- Ninguno")
    lines.extend(["", "## Recomendación", ""])
    for target, recommendation in matrix["recommendations"].items():
        lines.append(f"- `{target}`: `{recommendation['profile']}` — {recommendation['reason']}")
    lines.extend(
        [
            "",
            "Las cifras son del conjunto sintético y de la máquina declarada en `environment`.",
            "La recall de identidad exige una galería etiquetada; sin ella queda `sin_medicion`.",
            "Consulta `docs/benchmark-edge.md` antes de promover una variante a producción.",
            "",
        ]
    )
    return "\n".join(lines)


def _format(value: Any) -> str:
    return "—" if value is None else str(value)


def _bool_label(value: Any) -> str:
    if value is True:
        return "SÍ"
    if value is False:
        return "NO"
    return "—"


def write_outputs(matrix: dict[str, Any], output: str | Path) -> dict[str, Path]:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    csv_path = destination.with_suffix(".csv")
    markdown_path = destination.with_suffix(".md")
    destination.write_text(json.dumps(matrix, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    rows = [flatten_row(row) for row in matrix["results"]]
    fieldnames = sorted({key for row in rows for key in row})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    markdown_path.write_text(render_markdown(matrix), encoding="utf-8")
    return {"json": destination, "csv": csv_path, "markdown": markdown_path}
