from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from shared.auth import get_current_user
from app.exchanges.manager import exchange_manager
import structlog

router = APIRouter()
logger = structlog.get_logger()

class AccountCreate(BaseModel):
    exchange_slug: str = Field(..., pattern="^(binance|binance_testnet|bybit|okx|coinbase)$")
    account_name: str
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None
    is_testnet: bool = False
    is_default: bool = False

@router.post("/")
async def create_account(req: AccountCreate, user=Depends(get_current_user)):
    # Validate credentials by fetching balance
    try:
        ex = await exchange_manager.get_exchange(
            req.exchange_slug, req.api_key, req.api_secret, req.passphrase, req.is_testnet
        )
        balance = await ex.fetch_balance()
        await ex.close()
    except Exception as e:
        logger.error("exchange_auth_failed", error=str(e), exchange=req.exchange_slug)
        raise HTTPException(status_code=400, detail=f"Invalid exchange credentials: {str(e)}")

    return {
        "id": str(UUID(int=0)),
        "exchange": req.exchange_slug,
        "name": req.account_name,
        "balance_usd": balance.get("USDT", {}).get("total", 0),
        "is_testnet": req.is_testnet,
        "created_at": "2026-08-01T00:00:00Z"
    }

@router.get("/")
async def list_accounts(user=Depends(get_current_user)):
    return {"accounts": []}

@router.get("/{account_id}/balance")
async def get_balance(account_id: UUID, user=Depends(get_current_user)):
    return {
        "account_id": str(account_id),
        "total_usd": 125000.50,
        "available_usd": 98000.00,
        "assets": {
            "BTC": {"free": 1.25, "locked": 0.0, "usd_value": 84312.50},
            "ETH": {"free": 15.0, "locked": 0.0, "usd_value": 35687.00},
            "USDT": {"free": 50000.0, "locked": 0.0, "usd_value": 50000.0}
        }
    }
