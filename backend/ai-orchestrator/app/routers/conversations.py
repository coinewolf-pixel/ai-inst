from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from shared.database import get_db
from shared.auth import get_current_user
from shared.kafka_client import publish
import httpx
import os
import json
from datetime import datetime

router = APIRouter()
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4096
    tools: Optional[List[dict]] = None

class StrategyGenRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=5000)
    strategy_type: str = Field(..., pattern="^(mean_reversion|momentum|arbitrage|market_making|custom_ml|grid|dca)$")
    symbol: str
    timeframe: str = "1h"
    risk_profile: str = "moderate"

@router.post("/chat")
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens
    }
    if request.tools:
        payload["tools"] = request.tools

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="AI provider error")

    data = r.json()
    await publish("ai.conversations", {
        "user_id": user["id"],
        "model": request.model,
        "tokens": data["usage"]["total_tokens"],
        "timestamp": datetime.utcnow().isoformat()
    })

    return {
        "response": data["choices"][0]["message"]["content"],
        "usage": data["usage"],
        "model": request.model
    }

@router.post("/generate-strategy")
async def generate_strategy(req: StrategyGenRequest, user=Depends(get_current_user)):
    system_prompt = f"""You are NEXORUM AI Strategy Architect — an elite quantitative trading strategy generator.
Generate a complete, production-ready trading strategy configuration in JSON format.

Requirements:
- Strategy type: {req.strategy_type}
- Primary symbol: {req.symbol}
- Timeframe: {req.timeframe}
- Risk profile: {req.risk_profile}

The JSON must include:
1. entry_conditions (list of technical indicator rules)
2. exit_conditions (take profit, stop loss, trailing stop)
3. position_sizing (fixed, kelly, or volatility_adjusted)
4. risk_management (max_drawdown, daily_loss_limit, correlation_filters)
5. parameters (optimized hyperparameters with ranges)
6. backtest_config (date range, commission, slippage model)
7. ai_explanation (human-readable strategy thesis)

Respond ONLY with valid JSON. No markdown fences."""

    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Strategy generation failed")

    content = r.json()["choices"][0]["message"]["content"]
    strategy_json = json.loads(content)

    await publish("ai.strategies.generated", {
        "user_id": user["id"],
        "strategy_type": req.strategy_type,
        "symbol": req.symbol,
        "timestamp": datetime.utcnow().isoformat()
    })

    return {
        "strategy": strategy_json,
        "metadata": {
            "generated_by": "gpt-4o",
            "symbol": req.symbol,
            "risk_profile": req.risk_profile
        }
    }

@router.get("/conversations")
async def list_conversations(user=Depends(get_current_user)):
    # Placeholder — would query DB
    return {"conversations": [], "user_id": user["id"]}
