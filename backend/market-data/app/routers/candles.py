from fastapi import APIRouter, Depends
from typing import Optional
from shared.auth import get_current_user

router = APIRouter()

@router.get("/{symbol}")
async def get_candles(
    symbol: str,
    timeframe: str = "1h",
    exchange: str = "binance",
    limit: int = 100,
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    user=Depends(get_current_user)
):
    import random
    from datetime import datetime, timedelta

    base_price = 67450
    candles = []
    for i in range(limit):
        ts = datetime.utcnow() - timedelta(hours=limit-i)
        open_p = base_price + random.uniform(-200, 200)
        close_p = open_p + random.uniform(-150, 150)
        high_p = max(open_p, close_p) + random.uniform(0, 100)
        low_p = min(open_p, close_p) - random.uniform(0, 100)
        vol = random.uniform(100, 5000)
        candles.append({
            "timestamp": int(ts.timestamp() * 1000),
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": round(vol, 4)
        })

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "exchange": exchange,
        "candles": candles
    }
