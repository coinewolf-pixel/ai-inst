from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from shared.auth import get_current_user
from shared.kafka_client import publish
from datetime import datetime
import json

router = APIRouter()

class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    strategy_type: str = Field(..., pattern="^(mean_reversion|momentum|arbitrage|market_making|custom_ml|grid|dca)$")
    config: dict
    ai_prompt: Optional[str] = None
    ai_model: str = "gpt-4o"
    is_public: bool = False

class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|paused|archived)$")

@router.post("/")
async def create_strategy(req: StrategyCreate, user=Depends(get_current_user)):
    strategy_id = str(UUID(int=0))  # Placeholder — would insert to DB
    await publish("strategies.created", {
        "strategy_id": strategy_id,
        "user_id": user["id"],
        "type": req.strategy_type,
        "timestamp": datetime.utcnow().isoformat()
    })
    return {
        "id": strategy_id,
        "name": req.name,
        "status": "draft",
        "created_at": datetime.utcnow().isoformat()
    }

@router.get("/")
async def list_strategies(user=Depends(get_current_user), page: int = 1, page_size: int = 20):
    return {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size
    }

@router.get("/{strategy_id}")
async def get_strategy(strategy_id: UUID, user=Depends(get_current_user)):
    return {"id": str(strategy_id), "name": "Sample Strategy", "status": "draft"}

@router.patch("/{strategy_id}")
async def update_strategy(strategy_id: UUID, req: StrategyUpdate, user=Depends(get_current_user)):
    return {"id": str(strategy_id), "updated": True}

@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: UUID, user=Depends(get_current_user)):
    return {"id": str(strategy_id), "deleted": True}

@router.post("/{strategy_id}/backtest")
async def run_backtest(strategy_id: UUID, user=Depends(get_current_user)):
    return {
        "strategy_id": str(strategy_id),
        "backtest_id": str(UUID(int=0)),
        "status": "queued",
        "estimated_duration": "2m"
    }

@router.post("/{strategy_id}/deploy")
async def deploy_strategy(strategy_id: UUID, agent_name: Optional[str] = None, user=Depends(get_current_user)):
    agent_id = str(UUID(int=0))
    await publish("strategies.deployed", {
        "strategy_id": str(strategy_id),
        "agent_id": agent_id,
        "user_id": user["id"],
        "timestamp": datetime.utcnow().isoformat()
    })
    return {
        "strategy_id": str(strategy_id),
        "agent_id": agent_id,
        "agent_name": agent_name or f"Agent-{strategy_id[:8]}",
        "status": "deployed"
    }
