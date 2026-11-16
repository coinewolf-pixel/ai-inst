from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from shared.auth import get_current_user
from shared.kafka_client import publish
from datetime import datetime

router = APIRouter()

class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    strategy_id: UUID
    exchange_account_id: UUID
    config: dict = {}

class AgentControl(BaseModel):
    action: str = Field(..., pattern="^(start|pause|stop|restart)$")

@router.post("/")
async def create_agent(req: AgentCreate, user=Depends(get_current_user)):
    agent_id = str(UUID(int=0))
    await publish("agents.created", {
        "agent_id": agent_id,
        "user_id": user["id"],
        "strategy_id": str(req.strategy_id),
        "timestamp": datetime.utcnow().isoformat()
    })
    return {
        "id": agent_id,
        "name": req.name,
        "status": "idle",
        "created_at": datetime.utcnow().isoformat()
    }

@router.get("/")
async def list_agents(user=Depends(get_current_user), status: Optional[str] = None):
    return {"items": [], "total": 0}

@router.get("/{agent_id}")
async def get_agent(agent_id: UUID, user=Depends(get_current_user)):
    return {
        "id": str(agent_id),
        "name": "Alpha Agent",
        "status": "running",
        "strategy": {"name": "Momentum BTC"},
        "metrics": {
            "total_pnl": 12450.50,
            "win_rate": 0.62,
            "sharpe": 1.85,
            "trades_today": 12
        }
    }

@router.post("/{agent_id}/control")
async def control_agent(agent_id: UUID, req: AgentControl, user=Depends(get_current_user)):
    await publish("agents.control", {
        "agent_id": str(agent_id),
        "action": req.action,
        "user_id": user["id"],
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"agent_id": str(agent_id), "action": req.action, "status": "accepted"}

@router.get("/{agent_id}/logs")
async def get_agent_logs(agent_id: UUID, limit: int = 100, user=Depends(get_current_user)):
    return {
        "agent_id": str(agent_id),
        "logs": [
            {"level": "INFO", "message": "Signal generated: BUY BTC/USDT @ 67450", "ts": datetime.utcnow().isoformat()},
            {"level": "INFO", "message": "Order filled: 0.5 BTC @ 67452.30", "ts": datetime.utcnow().isoformat()},
            {"level": "WARN", "message": "Volatility spike detected, reducing position size", "ts": datetime.utcnow().isoformat()}
        ]
    }

@router.get("/{agent_id}/performance")
async def get_agent_performance(agent_id: UUID, user=Depends(get_current_user)):
    return {
        "agent_id": str(agent_id),
        "period": "30d",
        "total_return": 0.185,
        "sharpe_ratio": 1.92,
        "max_drawdown": -0.08,
        "win_rate": 0.64,
        "profit_factor": 2.1,
        "avg_trade": 145.5,
        "total_trades": 234
    }
