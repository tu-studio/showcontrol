from fastapi import WebSocket

from .seamless_listener import SeamlessListener, Point3D


class WSConnectionManager:
    def __init__(self, seamless_listener: SeamlessListener):
        self.active_connections: list[WebSocket] = []
        self.seamless_listener = seamless_listener

        # register connection manager with seamless listener
        seamless_listener.register_position_callback(self.send_position_update)
        seamless_listener.register_gain_callback(self.send_gain_update)
        seamless_listener.register_polygon_callback(self.send_polygon_update)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.send_full_position_update(websocket)
        print("active connections: ", len(self.active_connections))

    async def send_full_position_update(self, websocket: WebSocket):
        if self.seamless_listener is None:
            raise Exception("seamless listener is none, wth")
        for source in self.seamless_listener.sources:
            await websocket.send_json(
                {
                    "id": source.idx,
                    "position": {"x": source.x, "y": source.y, "z": source.z},
                    "gains": source.gain,
                }
            )
        await websocket.send_json(
            {
                "room_name": self.seamless_listener.room_name,
                "polygon": [p.to_dict() for p in self.seamless_listener.polygon],
            }
        )

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_position_update(self, source_id, x, y, z):
        for connection in self.active_connections:
            await connection.send_json(
                {"id": source_id, "position": {"x": x, "y": y, "z": z}}
            )

    async def send_gain_update(self, source_id, renderer_id, gain):
        for connection in self.active_connections:
            await connection.send_json(
                {"id": source_id, "renderer_id": renderer_id, "renderer_gain": gain}
            )

    async def send_polygon_update(self, room_name: str, polygon: list[Point3D]):
        for connection in self.active_connections:
            await connection.send_json(
                {"room_name": room_name, "polygon": [p.to_dict() for p in polygon]}
            )

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)
