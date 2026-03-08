"""
Algorand blockchain service for renewable certificates and bill integrity.
Handles SUN ASA transfers and bill hash recording.
"""

import logging
import base64
from algosdk.v2client import algod, indexer
from algosdk.transaction import (
    PaymentTxn,
    AssetTransferTxn,
    AssetConfigTxn,
)
from algosdk import account
from config import settings

logger = logging.getLogger(__name__)


class BlockchainService:
    """Manages Algorand blockchain operations for ROSHNI."""

    def __init__(self):
        """Initialize Algorand clients."""
        self.algod_client = algod.AlgodClient(
            "",
            settings.algorand_node_url,
        )
        self.indexer_client = indexer.IndexerClient(
            "",
            settings.algorand_indexer_url,
        )

        self.sun_asa_id = settings.sun_asa_id
        self.admin_public_key = None
        self.admin_private_key = None

        if settings.algorand_admin_private_key:
            self._setup_admin_account()

    # ================= ADMIN SETUP =================

    def _setup_admin_account(self):
        """Setup admin account using private key."""
        try:
            private_key = settings.algorand_admin_private_key.strip()
            self.admin_private_key = private_key
            self.admin_public_key = account.address_from_private_key(private_key)
            logger.info(f"✅ Admin account loaded: {self.admin_public_key}")
            logger.info(f"   Private key length: {len(private_key)}")
        except Exception as e:
            logger.error(f"❌ Failed to setup admin account: {str(e)}", exc_info=True)

    # ================= ASA CREATION =================

    def create_sun_asa(self) -> dict:
        """Create SUN ASA. 1 SUN = 1 kWh renewable certificate."""
        if not self.admin_public_key:
            return {"status": "error", "message": "Admin not configured"}

        try:
            params = self.algod_client.suggested_params()
            txn = AssetConfigTxn(
                sender=self.admin_public_key,
                sp=params,
                total=1_000_000_000,
                decimals=0,
                unit_name="SUN",
                asset_name="Solar Utility Note",
                manager=self.admin_public_key,
                reserve=self.admin_public_key,
                freeze=self.admin_public_key,
                clawback=self.admin_public_key,
                url="https://roshni.energy/sun",
            )
            signed_txn = txn.sign(self.admin_private_key)
            txid = self.algod_client.send_transaction(signed_txn)
            logger.info(f"SUN ASA creation submitted: {txid}")
            return {"status": "submitted", "tx_id": txid, "message": "SUN ASA creation transaction sent"}
        except Exception as e:
            logger.error(f"SUN ASA creation error: {str(e)}")
            return {"status": "error", "message": str(e)}

    # ================= ASA TRANSFER =================

    def transfer_sun_asa(self, recipient_address: str, amount_kwh: float, reason: str = "allocation") -> dict:
        """Transfer SUN ASA tokens to consumer."""
        logger.info(f"\n{'='*70}")
        logger.info(f"BLOCKCHAIN TRANSFER: {amount_kwh:.2f} SUN to {recipient_address}")
        logger.info(f"Reason: {reason}")
        logger.info(f"{'='*70}")
        
        if not self.sun_asa_id:
            logger.error("❌ SUN ASA not configured")
            return {"status": "error", "message": "SUN ASA not configured"}
        if not self.admin_private_key:
            logger.error("❌ Admin key not configured")
            return {"status": "error", "message": "Admin not configured"}

        try:
            logger.info(f"Admin Address: {self.admin_public_key}")
            logger.info(f"Recipient: {recipient_address}")
            logger.info(f"ASA ID: {self.sun_asa_id}")
            logger.info(f"Amount: {amount_kwh:.2f}")
            
            params = self.algod_client.suggested_params()
            logger.info(f"Got suggested params: fee={params.min_fee}")
            
            txn = AssetTransferTxn(
                sender=self.admin_public_key,
                sp=params,
                receiver=recipient_address,
                amt=int(amount_kwh),
                index=self.sun_asa_id,
            )
            logger.info(f"Transaction created")
            
            signed_txn = txn.sign(self.admin_private_key)
            logger.info(f"Transaction signed")
            
            txid = self.algod_client.send_transaction(signed_txn)
            logger.info(f"✅ Transaction submitted: {txid}")
            
            return {"status": "submitted", "tx_id": txid, "amount": amount_kwh, "recipient": recipient_address}
        except Exception as e:
            logger.error(f"❌ SUN transfer error: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # ================= BILL HASH RECORD =================

    def record_bill_hash(self, bill_hash: str, house_id: str, month_year: str) -> dict:
        """Record bill hash on blockchain as a 0-ALGO self-payment with note."""
        if not self.admin_private_key:
            return {"status": "error", "message": "Admin not configured"}

        try:
            params = self.algod_client.suggested_params()
            note_text = f"ROSHNI|{house_id}|{month_year}|{bill_hash}".encode()
            txn = PaymentTxn(
                sender=self.admin_public_key,
                sp=params,
                receiver=self.admin_public_key,
                amt=0,
                note=note_text,
            )
            signed_txn = txn.sign(self.admin_private_key)
            txid = self.algod_client.send_transaction(signed_txn)
            logger.info(f"Bill hash recorded: {txid}")
            return {"status": "submitted", "tx_id": txid, "house_id": house_id, "month_year": month_year}
        except Exception as e:
            logger.error(f"Bill hash error: {str(e)}")
            return {"status": "error", "message": str(e)}

    # ================= VERIFY BILL HASH =================

    def verify_bill_hash(self, txn_id: str) -> dict:
        """
        Verify a transaction on Algorand and decode its note field.
        Works for both bill hash transactions and any other ROSHNI txns.
        """
        try:
            # Fetch transaction from indexer
            txn_info = self.indexer_client.transaction(txn_id)
            txn = txn_info.get("transaction", {})

            if not txn:
                return {
                    "status": "not_found",
                    "txn_id": txn_id,
                    "note": None,
                    "message": "Transaction not found on Algorand testnet",
                }

            # Decode note field (base64 encoded on Algorand)
            note_b64 = txn.get("note", "")
            note_decoded = ""
            if note_b64:
                try:
                    note_decoded = base64.b64decode(note_b64).decode("utf-8")
                except Exception:
                    note_decoded = note_b64  # Return raw if decode fails

            # Determine if this is a ROSHNI bill hash transaction
            is_roshni = note_decoded.startswith("ROSHNI|")

            return {
                "status": "verified",
                "txn_id": txn_id,
                "note": note_decoded if note_decoded else None,
                "is_roshni_bill": is_roshni,
                "confirmed_round": txn.get("confirmed-round"),
                "sender": txn.get("sender"),
                "amount": txn.get("payment-transaction", {}).get("amount", 0),
                "explorer_url": f"https://testnet.algoexplorer.io/tx/{txn_id}",
            }

        except Exception as e:
            logger.error(f"Verify bill hash error for {txn_id}: {str(e)}")
            return {
                "status": "error",
                "txn_id": txn_id,
                "note": None,
                "message": str(e),
            }

    # ================= NETWORK INFO =================

    def get_network_params(self) -> dict:
        """Get Algorand network parameters."""
        try:
            status = self.algod_client.status()
            params = self.algod_client.suggested_params()
            return {
                "network": settings.algorand_network,
                "node_url": settings.algorand_node_url,   # ✅ Fix: was missing, used in frontend
                "latest_round": status.get("last-round"),
                "min_fee": params.min_fee,
                "sun_asa_id": self.sun_asa_id,
            }
        except Exception as e:
            logger.error(f"Network params error: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "network": settings.algorand_network,
                "node_url": settings.algorand_node_url,
                "latest_round": None,
                "min_fee": None,
                "sun_asa_id": self.sun_asa_id,
            }