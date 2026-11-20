"""Versión actual del contrato de eventos serializados.

Este valor vive junto a los DTOs para que los productores no necesiten importar
``shared.events`` (módulo de compatibilidad) y puedan declararlo como valor por
defecto de sus contratos.
"""

EVENT_SCHEMA_VERSION = "1.0.0"
