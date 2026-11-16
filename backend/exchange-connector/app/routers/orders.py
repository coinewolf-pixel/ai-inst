from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from shared.auth import get_current_user
from shared.kafka_client import publish
from datetime import datetime
import structlog

router = APIRouter()
logger = structlog.get_logger()

class OrderCreate(BaseModel):
    account_id: UUID
    symbol: str = Field(..., pattern="^[A-Z0-9]+/[A-Z0-9]+$")
    side: str = Field(..., pattern="^(buy|sell)$")
    order_type: str = Field(..., pattern="^(market|limit|stop_limit|stop_market)$")
    quantity: float = Field(..., gt=0)
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"

class OrderResponse(BaseModel):
    id: UUID
    exchange_order_id: Optional[str]
    symbol: str
    side: str
    status: str
    filled_quantity: float
    average_price: Optional[float]
    created_at: datetime

@router.post("/", response_model=OrderResponse)
async def create_order(req: OrderCreate, user=Depends(get_current_user)):
    order_id = UUID(int=0)

    await publish("orders.created", {
        "order_id": str(order_id),
        "user_id": user["id"],
        "symbol": req.symbol,
        "side": req.side,
        "quantity": req.quantity,
        "timestamp": datetime.utcnow().isoformat()
    })

    logger.info("order_created", order_id=str(order_id), symbol=req.symbol, side=req.side)

    return OrderResponse(
        id=order_id,
        exchange_order_id="sim_123456",
        symbol=req.symbol,
        side=req.side,
        status="open",
        filled_quantity=0.0,
        average_price=None,
        created_at=datetime.utcnow()
    )

@router.get("/")
async def list_orders(
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    user=Depends(get_current_user)
):
    return {"orders": [], "total": 0}

@router.get("/{order_id}")
async def get_order(order_id: UUID, user=Depends(get_current_user)):
    return {
        "id": str(order_id),
        "symbol": "BTC/USDT",
        "side": "buy",
        "status": "filled",
        "filled_quantity": 0.5,
        "average_price": 67450.00
    }

@router.delete("/{order_id}")
async def cancel_order(order_id: UUID, user=Depends(get_current_user)):
    await publish("orders.cancelled", {
        "order_id": str(order_id),
        "user_id": user["id"],
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"id": str(order_id), "status": "cancelled"}
