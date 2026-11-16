from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from shared.auth import get_current_user
from shared.kafka_client import publish
from datetime import datetime
import structlog

router = APIRouter()
logger = structlog.get_logger()

class LimitCreate(BaseModel):
    limit_type: str = Field(..., pattern="^(max_position_size|max_daily_loss|max_drawdown|max_leverage|max_orders_per_min|max_exposure|var_limit)$")
    symbol: Optional[str] = None
    value: float = Field(..., gt=0)
    is_hard_limit: bool = True
    agent_id: Optional[UUID] = None

@router.post("/")
async def create_limit(req: LimitCreate, user=Depends(get_current_user)):
    limit_id = UUID(int=0)
    await publish("risk.limits.created", {
        "limit_id": str(limit_id),
        "user_id": user["id"],
        "type": req.limit_type,
        "value": req.value,
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"id": str(limit_id), "type": req.limit_type, "value": req.value, "is_active": True}

@router.get("/")
async def list_limits(user=Depends(get_current_user), agent_id: Optional[UUID] = None):
    return {"limits": [], "total": 0}

@router.delete("/{limit_id}")
async def delete_limit(limit_id: UUID, user=Depends(get_current_user)):
    return {"id": str(limit_id), "deleted": True}
