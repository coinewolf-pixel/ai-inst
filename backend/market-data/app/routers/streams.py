from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from shared.auth import get_current_user

router = APIRouter()

class StreamRequest(BaseModel):
    symbols: List[str]
    channels: List[str] = ["ticker", "orderbook", "trades"]

@router.post("/subscribe")
async def subscribe_stream(req: StreamRequest, user=Depends(get_current_user)):
    return {
        "stream_id": "stream_001",
        "symbols": req.symbols,
        "channels": req.channels,
        "websocket_url": f"ws://localhost:8005/ws/BTC/USDT",
        "status": "active"
    }

@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str, exchange: str = "binance", user=Depends(get_current_user)):
    return {
        "symbol": symbol,
        "exchange": exchange,
        "last": 67450.25,
        "bid": 67449.50,
        "ask": 67451.00,
        "change_24h": 2.45,
        "volume_24h": 2850000000,
        "high_24h": 68100.00,
        "low_24h": 65800.00,
        "timestamp": "2026-08-01T12:00:00Z"
    }

@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, exchange: str = "binance", depth: int = 10, user=Depends(get_current_user)):
    return {
        "symbol": symbol,
        "exchange": exchange,
        "bids": [[67449.50, 2.5], [67448.00, 5.0], [67446.00, 12.3]],
        "asks": [[67451.00, 1.8], [67452.50, 4.2], [67455.00, 8.7]],
        "spread": 1.50,
        "timestamp": "2026-08-01T12:00:00Z"
    }
