from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)


from .ws_connection_manager import WSConnectionManager
from .seamless_listener import SeamlessListener
from pydantic import BaseModel


router = APIRouter()

seamless_listener: SeamlessListener | None = None
connection_manager: WSConnectionManager | None = None


async def get_connection_manager():
    # todo handle cm being none
    return connection_manager


class ServiceStatus(BaseModel):
    name: str
    load_state: str
    active_state: str
    sub_state: str


class Services(BaseModel):
    services: list[ServiceStatus]


pc_status: dict[str, dict[str, Services]] = {
    "test": {"kaorutest": Services(services=[])}
}


@router.websocket("/pos")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_manager: WSConnectionManager = Depends(get_connection_manager),
):
    # print("aah")
    await connection_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # TODO do something with that?
    except WebSocketDisconnect:

        connection_manager.disconnect(websocket)


@router.post("/servicestatus/{room_id}/{pc_id}")
async def update_service_status(room_id: str, pc_id: str, services: Services):
    if room_id not in pc_status:
        raise HTTPException(status_code=404, detail="Room not found")
    if pc_id not in pc_status[room_id]:
        raise HTTPException(status_code=404, detail="PC not found")

    pc_status[room_id][pc_id] = services
    print(services)
    return services


@router.get("/servicestatus/{room_id}")
async def get_service_status(room_id: str):
    if room_id not in pc_status:
        raise HTTPException(status_code=404, detail="Room not found")

    return pc_status[room_id]
