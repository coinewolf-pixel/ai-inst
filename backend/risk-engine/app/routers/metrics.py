from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from uuid import UUID
from shared.auth import get_current_user
import numpy as np
from datetime import datetime, timedelta

router = APIRouter()

class VaRRequest(BaseModel):
    portfolio_value: float
    returns: List[float]
    confidence: float = 0.95
    holding_days: int = 1

@router.post("/var")
async def calculate_var(req: VaRRequest, user=Depends(get_current_user)):
    returns = np.array(req.returns)
    var = np.percentile(returns, (1 - req.confidence) * 100)
    var_amount = abs(var) * req.portfolio_value * np.sqrt(req.holding_days)
    return {
        "var_daily": float(abs(var) * req.portfolio_value),
        "var_holding_period": float(var_amount),
        "confidence": req.confidence,
        "holding_days": req.holding_days,
        "method": "historical_simulation"
    }

@router.get("/portfolio/{user_id}")
async def get_portfolio_risk(user_id: UUID, current_user=Depends(get_current_user)):
    if str(user_id) != current_user["id"] and current_user["role"] != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")

    return {
        "user_id": str(user_id),
        "total_exposure_usd": 245000.00,
        "margin_utilization": 0.42,
        "largest_position": {"symbol": "BTC/USDT", "exposure_usd": 150000.00, "pct_of_portfolio": 0.61},
        "concentration_risk": "medium",
        "var_95_1d": 8500.00,
        "expected_shortfall": 12000.00,
        "stress_test_scenarios": {
            "btc_minus_20pct": {"portfolio_impact": -0.12, "usd_loss": -29400.00},
            "eth_minus_30pct": {"portfolio_impact": -0.08, "usd_loss": -19600.00},
            "correlation_spike": {"portfolio_impact": -0.15, "usd_loss": -36750.00}
        }
    }

@router.get("/agent/{agent_id}")
async def get_agent_risk(agent_id: UUID, user=Depends(get_current_user)):
    return {
        "agent_id": str(agent_id),
        "current_drawdown": 0.03,
        "max_drawdown_limit": 0.10,
        "daily_pnl": 2450.00,
        "daily_loss_limit": -5000.00,
        "open_positions": 3,
        "margin_used": 45000.00,
        "free_margin": 55000.00,
        "risk_score": 42,
        "status": "green"
    }
