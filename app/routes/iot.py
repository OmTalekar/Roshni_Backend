"""
IoT endpoints for solar generation updates.
NodeMCU devices push generation data here every 5 seconds.
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class IoTData(BaseModel):
    auth_token: str
    device_id: str
    generation_kwh: float
    house_id: str
    signal_strength: int


@router.post("/update")
async def update_iot(data: IoTData):
    """
    Receive solar generation update from IoT device.
    """
    print("Data received from ESP32:")
    print(data)

    return {
        "status": "success",
        "message": "Data received"
    }