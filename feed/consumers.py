import json
from channels.generic.websocket import AsyncWebsocketConsumer


class StatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.status_group_name = "status"
        await self.channel_layer.group_add(self.status_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.status_group_name, self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        await self.channel_layer.group_send(
            self.status_group_name, {"type": "status_message", "message": message}
        )

    async def status_message(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps({"message": message}))
