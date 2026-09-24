from domain.entities import Polygon
from infrastructure.door.polygon_door_analytics import PolygonDoorAnalytics

ext_poly = Polygon(name="ext", points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)))
int_poly = Polygon(name="int", points=((3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0)))


def _run_trayectoria(door, person_id, puntos):
    """Corre una secuencia de posiciones y devuelve la lista de eventos
    emitidos (sin los None)."""
    eventos = []
    for punto in puntos:
        event = door.update(person_id, punto)
        if event is not None:
            eventos.append(event)
    return eventos


def test_trayectoria_person_entered():
    door = PolygonDoorAnalytics(ext_poly, int_poly)

    # Persona camina desde fuera, pasa por exterior, y llega a interior
    trayectoria = [
        (15.0, 15.0),  # fuera
        (8.0, 8.0),    # exterior
        (2.0, 2.0),    # exterior (se acerca)
        (5.0, 5.0),    # interior (cruza)
        (5.5, 5.5),    # interior (se queda)
    ]

    eventos = _run_trayectoria(door, "p1", trayectoria)

    assert len(eventos) == 1
    assert eventos[0].event == "PERSON_ENTERED"
    assert eventos[0].person_id == "p1"


def test_trayectoria_person_exited():
    door = PolygonDoorAnalytics(ext_poly, int_poly)

    # Persona empieza adentro y sale hacia el exterior
    trayectoria = [
        (5.0, 5.0),    # interior
        (5.5, 5.5),    # interior (se queda un momento)
        (2.0, 2.0),    # exterior (cruza)
        (1.0, 1.0),    # exterior (se aleja)
    ]

    eventos = _run_trayectoria(door, "p1", trayectoria)

    assert len(eventos) == 1
    assert eventos[0].event == "PERSON_EXITED"
    assert eventos[0].person_id == "p1"


def test_trayectoria_false_alarm():
    door = PolygonDoorAnalytics(ext_poly, int_poly)

    # Persona toca la zona exterior pero nunca llega a interior, y se retira
    trayectoria = [
        (15.0, 15.0),  # fuera
        (1.0, 1.0),    # exterior (toca)
        (1.5, 1.5),    # exterior (duda)
        (20.0, 20.0),  # fuera (se retira sin haber llegado a interior)
    ]

    eventos = _run_trayectoria(door, "p1", trayectoria)

    assert len(eventos) == 1
    assert eventos[0].event == "FALSE_ALARM"
    assert eventos[0].person_id == "p1"
