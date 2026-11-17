"""OpenCV rendering for monitor frames."""
from dataclasses import asdict

import cv2
import numpy as np


def render_frame(frame, tracks, zones, analytics, label_for, demo=False):
    annotated = frame.copy()
    polygons = [] if demo else [(zones.exterior, (220, 175, 90)),
                                (zones.interior, (150, 210, 100)),
                                (zones.door, (70, 200, 240))]
    for polygon, color in polygons:
        points = np.array(polygon.points, dtype=np.int32)
        cv2.polylines(annotated, [points], True, color, 1, cv2.LINE_AA)
        x, y = points[0]
        cv2.putText(annotated, 'puerta' if polygon.name == 'door' else polygon.name,
                    (int(x)+5, int(y)+18), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1,
                    cv2.LINE_AA)
    people = []
    for track in tracks:
        history = analytics.get_history(track.person_id)
        zone = history[-1].zone if history else 'fuera'
        label = label_for(track.person_id)
        people.append({**asdict(track), 'zone': zone, 'display_name': label})
        box = track.bbox
        x1, y1, x2, y2 = map(int, (box.x1, box.y1, box.x2, box.y2))
        color = (150, 240, 175)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.circle(annotated, tuple(map(int, box.center)), 3, color, -1)
        cv2.putText(annotated, label, (x1, max(18, y1-8)),
                    cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(annotated, label, (x1, max(18, y1-8)),
                    cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
    ok, jpeg = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError('No se pudo codificar el frame')
    return jpeg.tobytes(), people
