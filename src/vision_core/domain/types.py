"""Tipos propios del dominio, independientes de librerías externas.

El dominio no conoce la representación concreta de un frame ni de un
embedding: solo los trata como valores opacos que los adaptadores de
infraestructura interpretan.
"""
from typing import Any, Sequence, TypeAlias

Frame: TypeAlias = Any
Embedding: TypeAlias = Sequence[float]
