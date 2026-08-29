"""Punto de entrada ASGI compatible al ejecutar desde la raíz del repositorio.

Se recomienda usar ``uvicorn mindcrafted.server:app`` o instalar primero con ``pip install -e .``.
"""

from mindcrafted.server import app

__all__ = ["app"]
