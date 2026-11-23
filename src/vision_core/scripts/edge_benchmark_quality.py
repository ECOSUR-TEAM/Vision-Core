import numpy as np

Box = tuple[float, float, float, float]


def box_iou(first: Box, second: Box) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    intersection = (x2 - x1) * (y2 - y1)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def match_boxes(
    predictions: list[Box], references: list[Box], *, threshold: float = 0.5
) -> list[tuple[int, int, float]]:
    candidates = []
    for prediction_index, prediction in enumerate(predictions):
        for reference_index, reference in enumerate(references):
            overlap = box_iou(prediction, reference)
            if overlap >= threshold:
                candidates.append((overlap, prediction_index, reference_index))
    candidates.sort(reverse=True)
    used_predictions: set[int] = set()
    used_references: set[int] = set()
    matches = []
    for overlap, prediction_index, reference_index in candidates:
        if prediction_index in used_predictions or reference_index in used_references:
            continue
        used_predictions.add(prediction_index)
        used_references.add(reference_index)
        matches.append((prediction_index, reference_index, round(overlap, 4)))
    return matches


def detection_quality(predictions: list[Box], references: list[Box]) -> dict:
    matches = match_boxes(predictions, references)
    return {
        "matches": len(matches),
        "predictions": len(predictions),
        "references": len(references),
        "precision_proxy": round(len(matches) / len(predictions), 4) if predictions else None,
        "map50_proxy": round(len(matches) / len(references), 4) if references else None,
        "mean_iou": round(sum(item[2] for item in matches) / len(matches), 4) if matches else None,
    }


def detection_quality_by_frame(predictions_by_frame: list[list[Box]], references_by_frame: list[list[Box]]) -> dict:
    frame_results = [
        detection_quality(predictions, references)
        for predictions, references in zip(predictions_by_frame, references_by_frame)
    ]
    matches = sum(result["matches"] for result in frame_results)
    predictions = sum(result["predictions"] for result in frame_results)
    references = sum(result["references"] for result in frame_results)
    ious = [
        item[2]
        for predictions_frame, references_frame in zip(predictions_by_frame, references_by_frame)
        for item in match_boxes(predictions_frame, references_frame)
    ]
    return {
        "matches": matches,
        "predictions": predictions,
        "references": references,
        "frames": len(frame_results),
        "precision_proxy": round(matches / predictions, 4) if predictions else None,
        "map50_proxy": round(matches / references, 4) if references else None,
        "mean_iou": round(sum(ious) / len(ious), 4) if ious else None,
    }


def identity_recall_at_1(
    variant: np.ndarray,
    reference: np.ndarray,
    *,
    expected_labels: np.ndarray | None = None,
    reference_labels: np.ndarray | None = None,
) -> float | None:
    if variant.size == 0 or reference.size == 0 or variant.ndim != 2 or reference.ndim != 2:
        return None
    if expected_labels is not None and reference_labels is not None:
        if len(expected_labels) != variant.shape[0] or len(reference_labels) != reference.shape[0]:
            return None
    elif expected_labels is not None or reference_labels is not None:
        return None
    elif variant.shape[0] != reference.shape[0]:
        return None
    variant_normalized = variant / np.maximum(np.linalg.norm(variant, axis=1, keepdims=True), 1e-12)
    reference_normalized = reference / np.maximum(np.linalg.norm(reference, axis=1, keepdims=True), 1e-12)
    similarities = variant_normalized @ reference_normalized.T
    nearest = np.argmax(similarities, axis=1)
    if expected_labels is not None and reference_labels is not None:
        predicted = np.asarray(reference_labels)[nearest]
        return round(float(np.mean(predicted == np.asarray(expected_labels))), 4)
    return round(float(np.mean(nearest == np.arange(len(variant)))), 4)


def evaluate_quality(quality: dict, baseline_quality: dict | None, gates: dict) -> dict:
    detection = quality.get("detection", {}).get("map50_proxy")
    identity = quality.get("identity", {}).get("recall_at_1_vs_gallery")
    if identity is None:
        identity = quality.get("identity", {}).get("recall_at_1_vs_fp32")
    max_drop = float(gates["max_relative_drop_pct"]) / 100
    checks: dict[str, dict] = {}
    for name, value, minimum in (
        ("detection_map50", detection, float(gates["min_detection_map50"])),
        ("identity_recall_at_1", identity, float(gates["min_identity_recall_at_1"])),
    ):
        if value is None:
            checks[name] = {"passed": False, "reason": "sin_medicion"}
            continue
        baseline_value = None
        if baseline_quality:
            baseline_section = (
                baseline_quality.get("detection", {})
                if name.startswith("detection")
                else (baseline_quality.get("identity", {}))
            )
            key = "map50_proxy" if name.startswith("detection") else "recall_at_1_vs_gallery"
            baseline_value = baseline_section.get(key)
            if baseline_value is None and not name.startswith("detection"):
                baseline_value = baseline_section.get("recall_at_1_vs_fp32")
        floor = baseline_value * (1 - max_drop) if baseline_value is not None else None
        passed = value >= minimum and (floor is None or value >= floor)
        checks[name] = {"passed": passed, "value": value, "minimum": minimum, "relative_floor": floor}
    return {
        "passed": all(item["passed"] for item in checks.values()),
        "evaluated_before_performance": True,
        "checks": checks,
    }
