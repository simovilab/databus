"""ASGI WebSocket consumer broadcasting schedule_engine build status to clients."""

import json
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer


class StatusConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer that joins the ``status`` group and relays build-status messages."""

    async def connect(self) -> None:
        """Join the ``status`` broadcast group and accept the WebSocket connection."""
        self.status_group_name = "status"
        await self.channel_layer.group_add(self.status_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        """Leave the ``status`` broadcast group when the socket disconnects."""
        await self.channel_layer.group_discard(
            self.status_group_name, self.channel_name
        )

    async def receive(self, text_data: str) -> None:
        """Re-broadcast an incoming client message to the ``status`` group."""
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        await self.channel_layer.group_send(
            self.status_group_name, {"type": "status_message", "message": message}
        )

    async def status_message(self, event: dict[str, Any]) -> None:
        """Forward a ``status_message`` group event to this consumer's socket."""
        message = event["message"]
        await self.send(text_data=json.dumps({"message": message}))
