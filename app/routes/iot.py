"""
IoT endpoints for solar generation updates.
NodeMCU devices push generation data here every 5 seconds.
"""
from fastapi import APIRouter, HTTPException
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


@router.get("/status/{house_id}")
async def get_iot_status(house_id: str):
    """
    Get current IoT device status for a house.
    Shows real-time generation, signal strength, and device info.
    """
    from app.services.iot_service import iot_service
    
    status = iot_service.get_device_status(house_id)
    
    if not status:
        return {
            "status": "offline",
            "house_id": house_id,
            "message": "No IoT data received yet",
        }
    
    return {
        "status": "online",
        "house_id": house_id,
        "device_id": status.get("device_id"),
        "generation_kwh": status.get("generation_kwh", 0),
        "signal_strength": status.get("signal_strength"),
        "last_update": status.get("last_update"),
        "cumulative_kwh": status.get("cumulative_kwh", 0),
    }