"""Pub/Sub Broker en memoria para distribución de eventos WebSocket.

Desacopla la producción de eventos (agente) del consumo (conexiones WebSocket).
"""

from typing import Callable, Optional
from collections import defaultdict
import asyncio
import inspect


class PubSubBroker:
    """Broker pub/sub en memoria con soporte para múltiples suscriptores.
    
    Un canal es una cadena como "chat.{session_id}".
    Cada callback se invoca asincronamente cuando se publica en su canal.
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    async def subscribe(self, channel: str, callback: Callable[[dict], None]) -> None:
        """Suscribir un callback a un canal.
        
        Args:
            channel: Nombre del canal (ej: "chat.{session_id}")
            callback: Función async o sync que recibe dict con el evento
        """
        self._subscribers[channel].append(callback)

    async def unsubscribe(self, channel: str, callback: Callable[[dict], None]) -> None:
        """Desuscribir un callback de un canal.
        
        Args:
            channel: Nombre del canal
            callback: La función que se desuscribe
        """
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(callback)
            except ValueError:
                pass

    async def publish(self, channel: str, message: dict) -> None:
        """Publicar un evento en un canal.
        
        Se invoca cada callback suscrito (de forma no bloqueante si es posible).
        
        Args:
            channel: Nombre del canal
            message: Diccionario con el evento (ej: {event, data, ...})
        """
        if channel not in self._subscribers:
            return

        # Ejecutar todos los callbacks sin esperar (fire and forget)
        tasks = []
        for callback in self._subscribers[channel]:
            if inspect.iscoroutinefunction(callback):
                tasks.append(callback(message))
            else:
                # Si es sync, envolver en una corrutina
                tasks.append(self._run_sync(callback, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _run_sync(func: Callable, *args, **kwargs):
        """Ejecutar función sync sin bloquear el event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def get_subscribers_count(self, channel: str) -> int:
        """Contar subscribers activos en un canal (para pruebas)."""
        return len(self._subscribers.get(channel, []))


# Instancia global del broker
_broker: Optional[PubSubBroker] = None


def get_pubsub_broker() -> PubSubBroker:
    """Obtener la instancia global del broker pub/sub."""
    global _broker
    if _broker is None:
        _broker = PubSubBroker()
    return _broker
