"""Evaluate recorded detections against manually annotated visible people."""
import argparse
import json
import math
from pathlib import Path


def iou(a, b):
    overlap = max(0, min(a[2],b[2])-max(a[0],b[0])) * max(0, min(a[3],b[3])-max(a[1],b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
    return overlap/union if union else 0


def box(values):
    if len(values) != 4 or not all(math.isfinite(v) for v in values) or values[2] <= values[0] or values[3] <= values[1]:
        raise ValueError('Bounding box xyxy inválido')
    return values


def evaluate(rows, truth, threshold=.5):
    if not 0 < threshold <= 1:
        raise ValueError('IoU debe estar entre 0 y 1')
    predictions = {}
    identities = {}
    for row in rows:
        if row['kind'] == 'detections':
            if row['frame'] in predictions:
                raise ValueError('Frame de detecciones duplicado')
            predictions[row['frame']] = row['detections']
        elif row['kind'] == 'resolved':
            identities[row['frame']] = row['persons']
    tp = fp = fn = switches = person_switches = identity_samples = 0
    previous_track, previous_person, seen = {}, {}, set()
    for frame in sorted(truth, key=lambda item: item['frame']):
        index = frame['frame']
        if index in seen or index not in predictions:
            raise ValueError('Frame anotado duplicado o ausente del registro')
        seen.add(index)
        gt, pred = frame['persons'], predictions[index]
        if len({p['id'] for p in gt}) != len(gt):
            raise ValueError('Identidad anotada duplicada en un frame')
        gt_boxes = [box(p['bbox']) for p in gt]
        pred_boxes = [box([p['bbox'][key] for key in ('x1','y1','x2','y2')]) for p in pred]
        candidates = sorted((-iou(a,b), i,j) for i,a in enumerate(gt_boxes) for j,b in enumerate(pred_boxes) if iou(a,b) >= threshold)
        used_gt, used_pred = set(), set()
        for _, i, j in candidates:
            if i in used_gt or j in used_pred:
                continue
            used_gt.add(i); used_pred.add(j)
            identity, track = gt[i]['id'], pred[j]['track_id']
            if identity in previous_track and previous_track[identity] != track:
                switches += 1
            previous_track[identity] = track
            resolved = identities.get(index, {}).get(str(track))
            if resolved is not None:
                identity_samples += 1
                if identity in previous_person and previous_person[identity] != resolved:
                    person_switches += 1
                previous_person[identity] = resolved
        tp += len(used_gt)
        fp += len(pred)-len(used_pred)
        fn += len(gt)-len(used_gt)
    return dict(annotated_frames=len(seen), true_positives=tp, false_positives=fp,
                missed_detections=fn, precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None, local_id_changes=switches,
                person_id_changes=person_switches if identity_samples else None,
                resolved_identity_samples=identity_samples, iou_threshold=threshold,
                matching='greedy descending IoU; changes compared to last matched observation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording'); parser.add_argument('annotations')
    parser.add_argument('--iou', type=float, default=.5)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.recording).read_text().splitlines()]
    truth = json.loads(Path(args.annotations).read_text())
    print(json.dumps(evaluate(rows, truth, args.iou), indent=2))


if __name__ == '__main__':
    main()
