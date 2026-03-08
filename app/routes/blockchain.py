"""
Blockchain endpoints for SUN ASA and bill hash operations.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime  # ✅ Fix: was at bottom of file, used before import
import logging

from app.schemas import ASATransferRequest, BillHashSubmit, BillHashResponse
from app.services.blockchain_service import BlockchainService

router = APIRouter()
logger = logging.getLogger(__name__)

blockchain_service = BlockchainService()


@router.get("/network-params")
async def get_network_params():
    """Get Algorand network parameters."""
    try:
        return blockchain_service.get_network_params()
    except Exception as e:
        logger.error(f"Network params error: {e}")
        raise HTTPException(status_code=503, detail="Algorand node unreachable")


@router.post("/sun-asa/create")
async def create_sun_asa():
    """
    Create SUN ASA (Solar Utility Note token).
    Only needs to be called once per deployment.
    """
    try:
        result = blockchain_service.create_sun_asa()
        logger.info(f"SUN ASA creation request: {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"SUN ASA create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sun-asa/transfer")
async def transfer_sun_asa(data: ASATransferRequest):
    """
    Transfer SUN ASA tokens to a house.
    Represents renewable allocation certificate.
    """
    try:
        result = blockchain_service.transfer_sun_asa(
            recipient_address=data.house_id,
            amount_kWh=data.amount,
            reason=data.reason,
        )
        logger.info(f"SUN ASA transfer: {data.amount:.2f} to {data.house_id}")
        return result
    except Exception as e:
        logger.error(f"SUN ASA transfer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bill-hash/submit", response_model=BillHashResponse)
async def submit_bill_hash(data: BillHashSubmit):
    """
    Submit monthly bill hash to Algorand for immutability proof.
    """
    try:
        result = blockchain_service.record_bill_hash(
            bill_hash=data.bill_hash,
            house_id=data.house_id,
            month_year=data.month_year,
        )
        logger.info(f"Bill hash submitted: {data.house_id}/{data.month_year}")
        return BillHashResponse(
            status=result.get("status"),
            bill_hash=data.bill_hash,
            blockchain_txn=result.get("message", "pending"),
            explorer_url="https://testnet.algoexplorer.io/",
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"Bill hash submit error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bill-hash/verify/{txn_id}")
async def verify_bill_hash(txn_id: str):
    """
    Verify bill hash on Algorand blockchain.
    Returns transaction details if found.
    """
    if not txn_id or len(txn_id) < 10:
        raise HTTPException(status_code=400, detail="Invalid transaction ID")

    try:
        result = blockchain_service.verify_bill_hash(txn_id)
        return result
    except Exception as e:
        logger.error(f"Bill hash verify error for {txn_id}: {e}")
        # Return a structured error instead of crashing — prevents CORS-like failures
        return {
            "status": "error",
            "txn_id": txn_id,
            "message": str(e),
            "note": None,
        }